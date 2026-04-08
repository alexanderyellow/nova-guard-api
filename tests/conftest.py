import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy.orm import sessionmaker

from nova_guard_api.core.config import get_settings
from nova_guard_api.db.base import Base
from nova_guard_api.db.session import get_db, get_engine, reset_engine
from nova_guard_api.main import app
from nova_guard_api.seed import seed_database


@pytest.fixture
def client(tmp_path) -> Generator[TestClient, None, None]:
    db_path = tmp_path / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    get_settings.cache_clear()
    reset_engine()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    ids = seed_database(db)
    db.close()

    def override_get_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        c.seed_ids = ids  # type: ignore[attr-defined]
        yield c
    app.dependency_overrides.clear()
    reset_engine()
    get_settings.cache_clear()
    os.environ.pop("DATABASE_URL", None)


def make_token(character_id: int) -> str:
    s = get_settings()
    return jwt.encode({"sub": str(character_id)}, s.jwt_secret, algorithm=s.jwt_algorithm)


def auth_headers(character_id: int, key: str = "test-admin-key") -> dict[str, str]:
    return {
        "X-Nova-Guard-Key": key,
        "Authorization": f"Bearer {make_token(character_id)}",
    }
