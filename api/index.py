"""Vercel serverless entry point.

Vercel's Python runtime detects the module-level `app` object as an ASGI app,
so we just re-export the existing FastAPI application from the `backend/`
package.

Request path: client → Vercel edge → rewrite `/api/*` to this function →
ASGI → FastAPI router → the same endpoints available locally at
`uvicorn app.main:app`.
"""

import sys
from pathlib import Path

# The repo layout keeps the server code under `backend/`. Vercel bundles the
# whole repository with the function (see `vercel.json → includeFiles`), so we
# just need to make `backend/` importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_BACKEND = _REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.main import app  # noqa: E402  (sys.path must be set up first)

__all__ = ["app"]
