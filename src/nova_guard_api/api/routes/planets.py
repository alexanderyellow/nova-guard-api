from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import require_any_auth
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor, require_admin
from nova_guard_api.db.models import Faction, FactionPlanet, Planet
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.factions import FactionOut
from nova_guard_api.schemas.planets import PlanetCreate, PlanetOut

router = APIRouter(prefix="/planets", tags=["planets"])


@router.get("")
def list_planets(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    biome: str | None = None,
    threat_level: int | None = None,
    faction_id: int | None = None,
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Planet)
    if biome:
        stmt = stmt.where(Planet.biome == biome)
    if threat_level is not None:
        stmt = stmt.where(Planet.threat_level == threat_level)
    if faction_id is not None:
        stmt = stmt.where(
            (Planet.ruling_faction_id == faction_id)
            | Planet.id.in_(select(FactionPlanet.planet_id).where(FactionPlanet.faction_id == faction_id))
        )
    rows, next_c = run_paginated(db, stmt, Planet.id, limit=limit, cursor=cursor)
    items = [PlanetOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.get("/{planet_id}", response_model=PlanetOut)
def get_planet(
    planet_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Planet, planet_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Planet not found")
    return row


@router.get("/{planet_id}/factions")
def planet_factions(
    planet_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    planet = db.get(Planet, planet_id)
    if planet is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Planet not found")
    ids = set()
    if planet.ruling_faction_id:
        ids.add(planet.ruling_faction_id)
    for fp in db.scalars(select(FactionPlanet).where(FactionPlanet.planet_id == planet_id)).all():
        ids.add(fp.faction_id)
    factions = []
    for fid in ids:
        f = db.get(Faction, fid)
        if f:
            factions.append(FactionOut.model_validate(f).model_dump())
    return {"planet_id": planet_id, "factions": factions}


@router.post("", response_model=PlanetOut, status_code=status.HTTP_201_CREATED)
def create_planet(
    body: PlanetCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = Planet(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/{planet_id}", response_model=PlanetOut)
def put_planet(
    planet_id: int,
    body: PlanetCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Planet, planet_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Planet not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{planet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_planet(
    planet_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Planet, planet_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Planet not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
