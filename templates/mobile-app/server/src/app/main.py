"""Mobile-app companion backend — minimal Pattern-A FastAPI service.

Serves the React Native client's two contract endpoints: `GET /health` (liveness)
and `GET /app-config` (remote force-update / kill-switch / feature toggles via the
vendored `mobile_config` module). Minimal default ships with NO database and NO
auth (`needs_database: false`, `has_bearer_api: false` in `defaults.yaml`) — flip
both when opting into `fabrik-lib/fastapi-user-auth` + `postgres-main`.

Deployed via `fabrik apply` (SSH + Docker Compose) like any other Pattern-A
service; the mobile client's `EXPO_PUBLIC_API_URL` points at it.
"""

from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import app_config, health

app = FastAPI(title="mobile-app-backend")

# A native RN client doesn't enforce CORS, but a permissive-but-configurable
# policy keeps a future web admin panel / Expo web build working without code
# changes. Empty CORS_ALLOW_ORIGINS (default) disables cross-origin entirely.
_cors_origins = [o for o in os.getenv("CORS_ALLOW_ORIGINS", "").split(",") if o]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(app_config.router)
