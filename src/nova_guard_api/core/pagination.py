import base64
import json
from typing import Any, TypeVar

from sqlalchemy import Select
from sqlalchemy.orm import Session

T = TypeVar("T")


def encode_cursor(last_id: int) -> str:
    raw = json.dumps({"id": last_id}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str | None) -> int | None:
    if not cursor:
        return None
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode())
        return int(data["id"])
    except (ValueError, KeyError, json.JSONDecodeError):
        return None


def run_paginated(
    db: Session,
    base_stmt: Select[tuple[T]],
    id_column,
    *,
    limit: int = 20,
    cursor: str | None = None,
) -> tuple[list[T], str | None]:
    lim = min(max(1, limit), 100)
    last_id = decode_cursor(cursor)
    stmt = base_stmt
    if last_id is not None:
        stmt = stmt.where(id_column > last_id)
    stmt = stmt.order_by(id_column).limit(lim + 1)
    rows = list(db.scalars(stmt).all())
    has_more = len(rows) > lim
    rows = rows[:lim]
    next_cursor = None
    if has_more and rows:
        next_cursor = encode_cursor(rows[-1].id)
    return rows, next_cursor


def hateoas_links(*, self_href: str, next_cursor: str | None = None) -> dict[str, Any]:
    links: dict[str, Any] = {"self": {"href": self_href}}
    if next_cursor:
        sep = "&" if "?" in self_href else "?"
        links["next"] = {"href": f"{self_href}{sep}cursor={next_cursor}"}
    return links
