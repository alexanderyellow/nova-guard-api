from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import require_any_auth
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor, require_admin
from nova_guard_api.db.models import Faction, Mission
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.factions import FactionCreate, FactionOut
from nova_guard_api.schemas.missions import MissionOut

router = APIRouter(prefix="/factions", tags=["factions"])


@router.get("")
def list_factions(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Faction)
    rows, next_c = run_paginated(db, stmt, Faction.id, limit=limit, cursor=cursor)
    items = [FactionOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.get("/{faction_id}", response_model=FactionOut)
def get_faction(
    faction_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Faction, faction_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faction not found")
    return row


@router.get("/{faction_id}/bounty-board")
def bounty_board(
    faction_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    fac = db.get(Faction, faction_id)
    if fac is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faction not found")
    missions = db.scalars(select(Mission).where(Mission.issuer_faction_id == faction_id)).all()
    return {
        "faction_id": faction_id,
        "missions": [MissionOut.model_validate(m).model_dump() for m in missions],
    }


@router.post("", response_model=FactionOut, status_code=status.HTTP_201_CREATED)
def create_faction(
    body: FactionCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = Faction(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{faction_id}", response_model=FactionOut)
def put_faction(
    faction_id: int,
    body: FactionCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Faction, faction_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faction not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{faction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faction(
    faction_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Faction, faction_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Faction not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
