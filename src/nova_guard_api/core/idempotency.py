import json
from typing import Any

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.db.models import IdempotencyRecord


def idempotency_scope(request: Request, suffix: str = "") -> str:
    return f"{request.method}:{request.url.path}{suffix}"


def get_cached_response(db: Session, key: str, scope: str) -> tuple[int, dict[str, Any]] | None:
    row = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == key,
            IdempotencyRecord.route == scope,
        )
    )
    if row is None:
        return None
    try:
        body = json.loads(row.response_body)
    except json.JSONDecodeError:
        body = {}
    return row.response_status, body


def store_response(db: Session, key: str, scope: str, status_code: int, body: dict) -> None:
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.key == key,
            IdempotencyRecord.route == scope,
        )
    )
    raw = json.dumps(body)
    if existing:
        existing.response_status = status_code
        existing.response_body = raw
    else:
        db.add(
            IdempotencyRecord(
                key=key,
                route=scope,
                response_status=status_code,
                response_body=raw,
            )
        )
    db.commit()
