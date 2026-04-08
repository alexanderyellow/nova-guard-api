from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import is_admin, require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor
from nova_guard_api.db.models import CharacterRole, Mission, MissionStatus
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.missions import (
    MissionAcceptBody,
    MissionBulkCreate,
    MissionCreate,
    MissionOut,
    MissionPatch,
)
from nova_guard_api.services.rules import assert_mission_accept_allowed, load_squad_with_members
from nova_guard_api.services.webhooks import dispatch_webhook_sync

router = APIRouter(prefix="/missions", tags=["missions"])


def can_post_mission(actor: Actor) -> bool:
    return is_admin(actor) or actor.role == CharacterRole.dealer


def can_patch_mission(actor: Actor) -> bool:
    return is_admin(actor) or actor.role == CharacterRole.dealer


@router.get("")
def list_missions(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    status_filter: MissionStatus | None = Query(default=None, alias="status"),
    danger: int | None = None,
    danger_max: int | None = None,
    faction_id: int | None = None,
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Mission)
    if status_filter is not None:
        stmt = stmt.where(Mission.status == status_filter)
    if danger is not None:
        stmt = stmt.where(Mission.danger_rating == danger)
    if danger_max is not None:
        stmt = stmt.where(Mission.danger_rating <= danger_max)
    if faction_id is not None:
        stmt = stmt.where(Mission.issuer_faction_id == faction_id)
    rows, next_c = run_paginated(db, stmt, Mission.id, limit=limit, cursor=cursor)
    items = [MissionOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.post("", response_model=MissionOut, status_code=status.HTTP_201_CREATED)
def create_mission(
    request: Request,
    body: MissionCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not can_post_mission(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot create missions")
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    row = Mission(
        **body.model_dump(),
        status=MissionStatus.available,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = MissionOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.post("/bulk", status_code=status.HTTP_201_CREATED)
def bulk_missions(
    request: Request,
    body: MissionBulkCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    if not is_admin(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin only")
    created = []
    for m in body.missions:
        row = Mission(**m.model_dump(), status=MissionStatus.available)
        db.add(row)
        db.flush()
        created.append(MissionOut.model_validate(row).model_dump())
    db.commit()
    return {"created": created, "count": len(created)}


@router.get("/{mission_id}", response_model=MissionOut)
def get_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Mission, mission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mission not found")
    return row


@router.patch("/{mission_id}", response_model=MissionOut)
def patch_mission(
    mission_id: int,
    body: MissionPatch,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    if not can_patch_mission(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot update missions")
    row = db.get(Mission, mission_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mission not found")
    data = body.model_dump(exclude_unset=True)
    old_status = row.status
    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    if old_status != row.status:
        dispatch_webhook_sync(
            "mission.status_changed",
            {
                "mission_id": mission_id,
                "old_status": old_status.value,
                "new_status": row.status.value,
            },
        )
    return row


@router.post("/{mission_id}/accept", response_model=MissionOut)
def accept_mission(
    mission_id: int,
    body: MissionAcceptBody,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mission not found")
    squad = load_squad_with_members(db, body.squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    assert_mission_accept_allowed(db, mission, squad, actor.character)
    mission.squad_id = body.squad_id
    mission.status = MissionStatus.accepted
    db.commit()
    db.refresh(mission)
    dispatch_webhook_sync(
        "mission.status_changed",
        {
            "mission_id": mission_id,
            "old_status": MissionStatus.available.value,
            "new_status": mission.status.value,
            "squad_id": body.squad_id,
        },
    )
    return mission


@router.post("/{mission_id}/complete", response_model=MissionOut)
def complete_mission(
    mission_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    mission = db.get(Mission, mission_id)
    if mission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Mission not found")
    if mission.squad_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Mission has no assigned squad")
    squad = load_squad_with_members(db, mission.squad_id)
    if squad is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Squad not found")
    if squad.captain_character_id != actor.id and not is_admin(actor):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Only the assigned squad captain can complete",
        )
    old = mission.status
    mission.status = MissionStatus.completed
    db.commit()
    db.refresh(mission)
    dispatch_webhook_sync(
        "mission.status_changed",
        {
            "mission_id": mission_id,
            "old_status": old.value,
            "new_status": mission.status.value,
        },
    )
    return mission
