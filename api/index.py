# ponytail: entrypoint adapter for Vercel serverless Python runtime
import sys
from pathlib import Path

# Add backend directory to sys.path so app imports resolve cleanly
backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi import Request
from app.main import app  # noqa: E402, F401
from app.db.init_db import init_db  # noqa: E402

# Guarantee DB schema and volume initialization on cold start
try:
    init_db()
except Exception:
    pass

@app.middleware("http")
async def vercel_path_rewrite_middleware(request: Request, call_next):
    # If Vercel passed __subpath via rewrite, restore real API route in scope['path']
    subpath = request.query_params.get("__subpath")
    if subpath is not None:
        clean_sub = subpath.strip("/")
        request.scope["path"] = f"/api/{clean_sub}" if clean_sub else "/api"
    response = await call_next(request)
    return response


