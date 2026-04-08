"""CLI entrypoint. Ensures `src` is on the path so `nova_guard_api` resolves."""

import sys
from pathlib import Path

import uvicorn

_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

if __name__ == "__main__":
    uvicorn.run("nova_guard_api.main:app", host="0.0.0.0", port=8000, reload=True)
