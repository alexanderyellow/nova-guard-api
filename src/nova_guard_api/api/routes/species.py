from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor, require_admin
from nova_guard_api.db.models import Species
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.species import SpeciesCreate, SpeciesOut

router = APIRouter(prefix="/species", tags=["species"])


@router.get("")
def list_species(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Species)
    rows, next_c = run_paginated(db, stmt, Species.id, limit=limit, cursor=cursor)
    items = [SpeciesOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.get("/{species_id}", response_model=SpeciesOut)
def get_species(
    species_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Species, species_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Species not found")
    return row


@router.post("", response_model=SpeciesOut, status_code=status.HTTP_201_CREATED)
def create_species(
    request: Request,
    body: SpeciesCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    row = Species(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = SpeciesOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.put("/{species_id}", response_model=SpeciesOut)
def replace_species(
    species_id: int,
    body: SpeciesCreate,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Species, species_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Species not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{species_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_species(
    species_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_admin),
):
    row = db.get(Species, species_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Species not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
