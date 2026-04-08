from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from nova_guard_api.core.idempotency import get_cached_response, idempotency_scope
from nova_guard_api.core.security import Actor, get_actor
from nova_guard_api.db.models import CharacterRole, Squad, SquadMember


def require_any_auth(actor: Actor = Depends(get_actor)) -> Actor:
    return actor


def is_admin(actor: Actor) -> bool:
    return actor.role == CharacterRole.admin


def is_captain_of_squad(db: Session, actor: Actor, squad_id: int) -> bool:
    squad = db.get(Squad, squad_id)
    return squad is not None and squad.captain_character_id == actor.id


def character_in_squad(db: Session, character_id: int, squad_id: int) -> bool:
    if db.get(Squad, squad_id) is None:
        return False
    sq = db.get(Squad, squad_id)
    if sq and sq.captain_character_id == character_id:
        return True
    row = db.scalar(
        select(SquadMember).where(
            SquadMember.squad_id == squad_id,
            SquadMember.character_id == character_id,
        )
    )
    return row is not None


def assert_can_manage_squad(db: Session, actor: Actor, squad_id: int) -> None:
    if is_admin(actor):
        return
    if is_captain_of_squad(db, actor, squad_id):
        return
    raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Not allowed to manage this squad")


def maybe_idempotent_hit(request: Request, db: Session, key: str | None) -> tuple[int, dict] | None:
    if not key:
        return None
    scope = idempotency_scope(request)
    return get_cached_response(db, key, scope)
