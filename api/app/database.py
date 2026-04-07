"""asyncpg connection pool management.

Exposes:
  - init_db(app)  — called in lifespan to create/close the pool on app.state
  - get_db()      — FastAPI dependency yielding a connection from the pool
"""

from __future__ import annotations

import os
import pathlib
from typing import AsyncGenerator

import asyncpg
import structlog
from fastapi import FastAPI, Request

logger = structlog.get_logger(__name__)


def _read_secret(env_var: str, default: str = "") -> str:
    """Return value from secret file (if <env_var>_FILE is set) or env var."""
    file_path = os.environ.get(f"{env_var}_FILE")
    if file_path:
        p = pathlib.Path(file_path)
        if p.exists():
            return p.read_text().strip()
    return os.environ.get(env_var, default)


def _build_db_dsn() -> str:
    """Construct a plain postgresql:// DSN usable by asyncpg."""
    base = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://track:DOCKER-SECRET@db:5432/trackdb",
    )
    password = _read_secret("DB_PASSWORD")
    dsn = base.replace("DOCKER-SECRET", password)
    # asyncpg requires the plain postgresql:// scheme
    return dsn.replace("postgresql+asyncpg://", "postgresql://")


async def init_db(app: FastAPI) -> None:
    """Create the asyncpg connection pool and store it on app.state."""
    dsn = _build_db_dsn()
    try:
        app.state.db_pool = await asyncpg.create_pool(
            dsn=dsn,
            min_size=2,
            max_size=10,
            command_timeout=10,
        )
        logger.info("Database pool created")
    except Exception as exc:
        logger.error("Failed to create database pool", error=str(exc))
        app.state.db_pool = None


async def close_db(app: FastAPI) -> None:
    """Close the asyncpg connection pool."""
    pool = getattr(app.state, "db_pool", None)
    if pool:
        await pool.close()
        logger.info("Database pool closed")


async def get_db(request: Request) -> AsyncGenerator[asyncpg.Connection, None]:
    """FastAPI dependency — yields a connection acquired from the pool."""
    pool: asyncpg.Pool | None = getattr(request.app.state, "db_pool", None)
    if pool is None:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        )
    async with pool.acquire() as conn:
        yield conn
