from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from nova_guard_api.core.config import get_settings, parse_api_keys
from nova_guard_api.db.models import Character, CharacterRole
from nova_guard_api.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class Actor:
    character: Character

    @property
    def id(self) -> int:
        return self.character.id

    @property
    def role(self) -> CharacterRole:
        return self.character.role


def require_api_key(x_nova_guard_key: str | None = Header(default=None)) -> None:
    if not x_nova_guard_key:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Nova-Guard-Key header",
        )
    keys = parse_api_keys(get_settings().api_keys)
    if x_nova_guard_key not in keys:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")


def get_actor(
    _: None = Depends(require_api_key),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Actor:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization Bearer token",
        )
    settings = get_settings()
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if sub is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
        cid = int(sub)
    except (JWTError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    char = db.get(Character, cid)
    if char is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Character not found")
    return Actor(character=char)


def require_roles(*allowed: CharacterRole):
    def _dep(actor: Actor = Depends(get_actor)) -> Actor:
        if actor.role not in allowed:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {[r.value for r in allowed]}",
            )
        return actor

    return _dep


def require_admin(actor: Actor = Depends(get_actor)) -> Actor:
    if actor.role != CharacterRole.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Admin only")
    return actor


def optional_actor(
    x_nova_guard_key: str | None = Header(default=None),
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Actor | None:
    if not x_nova_guard_key:
        return None
    keys = parse_api_keys(get_settings().api_keys)
    if x_nova_guard_key not in keys:
        return None
    if creds is None or creds.scheme.lower() != "bearer":
        return None
    try:
        settings = get_settings()
        payload = jwt.decode(
            creds.credentials,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        sub = payload.get("sub")
        if sub is None:
            return None
        cid = int(sub)
        char = db.get(Character, cid)
        if char is None:
            return None
        return Actor(character=char)
    except (JWTError, ValueError, TypeError):
        return None
