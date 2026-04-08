from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import character_in_squad, is_admin, require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor, require_admin
from nova_guard_api.db.models import Character, CharacterRole, Squad
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.characters import BountyUpdate, CharacterCreate, CharacterOut, CharacterPatch

router = APIRouter(prefix="/characters", tags=["characters"])


def can_view_character(db: Session, actor: Actor, target_id: int) -> bool:
    if is_admin(actor):
        return True
    if actor.id == target_id:
        return True
    if actor.role == CharacterRole.dealer:
        return True
    if actor.role == CharacterRole.captain:
        squads = db.scalars(select(Squad).where(Squad.captain_character_id == actor.id)).all()
        for s in squads:
            if character_in_squad(db, target_id, s.id):
                return True
    return False


@router.get("")
def list_characters(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Character)
    rows, next_c = run_paginated(db, stmt, Character.id, limit=limit, cursor=cursor)
    items = [CharacterOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.post("", response_model=CharacterOut, status_code=status.HTTP_201_CREATED)
def create_character(
    request: Request,
    body: CharacterCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    row = Character(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = CharacterOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.get("/{character_id}", response_model=CharacterOut)
def get_character(
    character_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(Character, character_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    if not can_view_character(db, actor, character_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot view this character")
    return row


@router.patch("/{character_id}", response_model=CharacterOut)
def patch_character(
    character_id: int,
    body: CharacterPatch,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(Character, character_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    if not is_admin(actor) and actor.id != character_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Can only update own profile")
    data = body.model_dump(exclude_unset=True)
    if not data:
        return row
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_character(
    character_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Character, character_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{character_id}/gear")
def get_gear(
    character_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(Character, character_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    if not can_view_character(db, actor, character_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot view gear")
    return {"character_id": character_id, "gear": row.gear}


@router.put("/{character_id}/bounty", response_model=CharacterOut)
def put_bounty(
    character_id: int,
    body: BountyUpdate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Character, character_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Character not found")
    old = row.bounty_credits
    row.bounty_credits = body.bounty_credits
    db.commit()
    db.refresh(row)
    from nova_guard_api.services.webhooks import dispatch_webhook_sync

    dispatch_webhook_sync(
        "bounty.updated",
        {"character_id": character_id, "old_bounty": old, "new_bounty": row.bounty_credits},
    )
    return row
