from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import assert_can_manage_squad, is_admin, require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor
from nova_guard_api.db.models import Character, CharacterRole, Squad, SquadMember
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.squads import SquadCreate, SquadMemberAdd, SquadOut, SquadPatch
from nova_guard_api.services.rules import (
    assert_squad_has_capacity,
    load_squad_with_members,
    parse_if_match,
    weak_etag_squad,
)

router = APIRouter(prefix="/squads", tags=["squads"])


def can_create_squad(actor: Actor) -> bool:
    return is_admin(actor) or actor.role == CharacterRole.captain


@router.get("")
def list_squads(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Squad)
    rows, next_c = run_paginated(db, stmt, Squad.id, limit=limit, cursor=cursor)
    items = [SquadOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.post("", response_model=SquadOut, status_code=status.HTTP_201_CREATED)
def create_squad(
    request: Request,
    body: SquadCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not can_create_squad(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot create squads")
    if not is_admin(actor):
        if actor.id != body.captain_character_id:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail="Captains can only create squads with themselves as captain",
            )
    cap = db.get(Character, body.captain_character_id)
    if cap is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Captain character not found")
    if cap.role != CharacterRole.captain and not is_admin(actor):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Captain character must have captain role",
        )
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    row = Squad(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = SquadOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.get("/{squad_id}")
def get_squad(
    squad_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Squad, squad_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    payload = SquadOut.model_validate(row).model_dump()
    return JSONResponse(
        content=payload,
        headers={"ETag": weak_etag_squad(squad_id)},
    )


@router.patch("/{squad_id}", response_model=SquadOut)
def patch_squad(
    squad_id: int,
    body: SquadPatch,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    if_match: str | None = Header(default=None, alias="If-Match"),
):
    squad = load_squad_with_members(db, squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    assert_can_manage_squad(db, actor, squad_id)
    expected = weak_etag_squad(squad_id)
    if if_match:
        got = parse_if_match(if_match)
        exp = parse_if_match(expected)
        if got != exp:
            raise HTTPException(status.HTTP_412_PRECONDITION_FAILED, detail="ETag mismatch")
    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(squad, k, v)
    db.commit()
    db.refresh(squad)
    return squad


@router.delete("/{squad_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_squad(
    squad_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    squad = db.get(Squad, squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    assert_can_manage_squad(db, actor, squad_id)
    db.delete(squad)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{squad_id}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_member(
    squad_id: int,
    body: SquadMemberAdd,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    squad = load_squad_with_members(db, squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    assert_can_manage_squad(db, actor, squad_id)
    assert_squad_has_capacity(squad, db)
    ch = db.get(Character, body.character_id)
    if ch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    existing = db.scalar(
        select(SquadMember).where(
            SquadMember.squad_id == squad_id,
            SquadMember.character_id == body.character_id,
        )
    )
    if existing:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if body.character_id == squad.captain_character_id:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    db.add(SquadMember(squad_id=squad_id, character_id=body.character_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{squad_id}/members/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    squad_id: int,
    character_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    squad = db.get(Squad, squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    assert_can_manage_squad(db, actor, squad_id)
    if character_id == squad.captain_character_id:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot remove the captain from the squad roster this way",
        )
    row = db.scalar(
        select(SquadMember).where(
            SquadMember.squad_id == squad_id,
            SquadMember.character_id == character_id,
        )
    )
    if row:
        db.delete(row)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
