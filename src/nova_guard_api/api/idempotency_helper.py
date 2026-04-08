from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from nova_guard_api.api.deps import maybe_idempotent_hit
from nova_guard_api.core.idempotency import idempotency_scope, store_response


def replay_if_idempotent(request: Request, db: Session, idempotency_key: str | None) -> JSONResponse | None:
    if not idempotency_key:
        return None
    hit = maybe_idempotent_hit(request, db, idempotency_key)
    if hit is None:
        return None
    sc, data = hit
    return JSONResponse(status_code=sc, content=data)


def save_idempotent(
    request: Request,
    db: Session,
    idempotency_key: str | None,
    status_code: int,
    body: dict,
) -> None:
    if idempotency_key:
        store_response(db, idempotency_key, idempotency_scope(request), status_code, body)
