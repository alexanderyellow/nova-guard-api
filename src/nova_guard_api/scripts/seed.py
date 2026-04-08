#!/usr/bin/env python3
"""Run from repo root: uv run python scripts/seed.py"""

import subprocess
import sys
from pathlib import Path

from sqlalchemy.orm import sessionmaker

# Repository root (contains alembic.ini)
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        check=True,
    )
    from nova_guard_api.core.config import get_settings
    from nova_guard_api.db.session import get_engine, reset_engine
    from nova_guard_api.seed import seed_database

    get_settings.cache_clear()
    reset_engine()
    Session = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    db = Session()
    try:
        ids = seed_database(db)
        print("Seed complete. Key ids:", ids)
    finally:
        db.close()


if __name__ == "__main__":
    main()
