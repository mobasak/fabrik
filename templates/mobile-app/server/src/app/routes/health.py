"""Liveness endpoint — never behind auth (Traefik/Authelia bypass by path).

Minimal default ships with `needs_database: false`, so there is no dependency to
probe and `{"status": "ok"}` is the real, complete health signal. If this project
flips `needs_database: true` in `defaults.yaml` (opting into `postgres-main`),
replace the body below with a real dependency check per `10-python.md`:

    from sqlalchemy import text
    from app.database import async_session

    @router.get("/health")
    async def health() -> dict[str, str]:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok"}
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
