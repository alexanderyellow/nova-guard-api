from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import is_admin, require_any_auth
from nova_guard_api.api.idempotency_helper import replay_if_idempotent, save_idempotent
from nova_guard_api.core.pagination import hateoas_links, run_paginated
from nova_guard_api.core.security import Actor
from nova_guard_api.db.models import Artifact, ArtifactRarity, CharacterRole, InfinityTransferJob
from nova_guard_api.db.session import get_db
from nova_guard_api.schemas.artifacts import ArtifactCreate, ArtifactOut, ArtifactTransfer

router = APIRouter(prefix="/artifacts", tags=["artifacts"])


def can_mutate_artifact(actor: Actor) -> bool:
    return is_admin(actor) or actor.role == CharacterRole.dealer


@router.get("")
def list_artifacts(
    request: Request,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
    cursor: str | None = None,
    limit: int = 20,
):
    stmt = select(Artifact)
    rows, next_c = run_paginated(db, stmt, Artifact.id, limit=limit, cursor=cursor)
    items = [ArtifactOut.model_validate(r).model_dump() for r in rows]
    self_href = str(request.url).split("?")[0]
    return {
        "items": items,
        "next_cursor": next_c,
        "_links": hateoas_links(self_href=self_href, next_cursor=next_c),
    }


@router.get("/{artifact_id}", response_model=ArtifactOut)
def get_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    _: Actor = Depends(require_any_auth),
):
    row = db.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    return row


@router.post("", response_model=ArtifactOut, status_code=status.HTTP_201_CREATED)
def create_artifact(
    request: Request,
    body: ArtifactCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not can_mutate_artifact(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot create artifacts")
    replay = replay_if_idempotent(request, db, idempotency_key)
    if replay:
        return replay
    row = Artifact(**body.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    out = ArtifactOut.model_validate(row).model_dump()
    save_idempotent(request, db, idempotency_key, 201, out)
    return row


@router.put("/{artifact_id}", response_model=ArtifactOut)
def put_artifact(
    artifact_id: int,
    body: ArtifactCreate,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    if not can_mutate_artifact(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot update artifacts")
    row = db.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    for k, v in body.model_dump().items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_artifact(
    artifact_id: int,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    if not can_mutate_artifact(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot delete artifacts")
    row = db.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{artifact_id}/transfer")
def transfer_artifact(
    artifact_id: int,
    body: ArtifactTransfer,
    db: Session = Depends(get_db),
    actor: Actor = Depends(require_any_auth),
):
    row = db.get(Artifact, artifact_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if not can_mutate_artifact(actor):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Cannot transfer artifacts")
    if (body.holder_character_id is None) == (body.holder_faction_id is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Exactly one of holder_character_id or holder_faction_id must be set",
        )
    if row.rarity == ArtifactRarity.infinity:
        if not is_admin(actor):
            job = InfinityTransferJob(
                artifact_id=artifact_id,
                target_character_id=body.holder_character_id,
                target_faction_id=body.holder_faction_id,
                status="pending",
                created_at=datetime.now(UTC),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            return JSONResponse(
                status_code=status.HTTP_202_ACCEPTED,
                content={
                    "job_id": job.id,
                    "status": "pending",
                    "message": "Infinity-class transfer requires admin approval",
                },
            )
        row.holder_character_id = body.holder_character_id
        row.holder_faction_id = body.holder_faction_id
        db.commit()
        db.refresh(row)
        return row
    row.holder_character_id = body.holder_character_id
    row.holder_faction_id = body.holder_faction_id
    db.commit()
    db.refresh(row)
    return row
