"""
track-mcp FastAPI application — Phase 2.

Provides:
  - /health                   liveness probe
  - /ready                    readiness probe (checks DB + Redis connectivity)
  - /api/v1/info              basic API metadata
  - /api/v1/auth/*            JWT auth endpoints
  - /api/v1/users/*           user profile endpoints
"""

from __future__ import annotations

import os
import pathlib
import time
from typing import Any

import structlog
import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.sessions import router as sessions_router
from app.api.vehicles import router as vehicles_router
from app.api.laps import router as laps_router
from app.api.telemetry import router as telemetry_router
from app.api.analysis import router as analysis_router
from app.api.coaching import router as coaching_router
from app.api.circuits import router as circuits_router
from app.api.corner_knowledge import router as corner_knowledge_router

# ---------------------------------------------------------------------------
# Logging setup (structlog → JSON in production, colored in dev)
# ---------------------------------------------------------------------------

LOG_LEVEL = os.environ.get("LOG_LEVEL", "info").upper()
ENVIRONMENT = os.environ.get("ENVIRONMENT", "development")

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        (
            structlog.dev.ConsoleRenderer()
            if ENVIRONMENT == "development"
            else structlog.processors.JSONRenderer()
        ),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(__import__("logging"), LOG_LEVEL, 20)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Helpers: read Docker secrets
# ---------------------------------------------------------------------------

def _read_secret(env_var: str, default: str = "") -> str:
    """Return value from secret file (if <env_var>_FILE is set) or env var."""
    file_path = os.environ.get(f"{env_var}_FILE")
    if file_path:
        p = pathlib.Path(file_path)
        if p.exists():
            return p.read_text().strip()
    return os.environ.get(env_var, default)


def _build_db_url() -> str:
    """Construct asyncpg-compatible DSN."""
    base = os.environ.get("DATABASE_URL", "postgresql+asyncpg://track:@db:5432/trackdb")
    password = _read_secret("DB_PASSWORD")
    return base.replace("DOCKER-SECRET", password)


def _build_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://redis:6379/0")


# ---------------------------------------------------------------------------
# Application lifespan (startup / shutdown)
# ---------------------------------------------------------------------------

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application-level resources."""
    logger.info("track-mcp API starting", environment=ENVIRONMENT)

    # Store startup timestamp for uptime reporting
    app.state.started_at = time.time()

    # Create asyncpg connection pool via database module
    from app.database import init_db as _init_db
    await _init_db(app)

    # Create a Redis connection
    try:
        app.state.redis = aioredis.from_url(
            _build_redis_url(),
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
        )
        await app.state.redis.ping()
        logger.info("Redis connection established")
    except Exception as exc:
        logger.error("Failed to connect to Redis", error=str(exc))
        app.state.redis = None

    logger.info("track-mcp API ready")

    yield  # --- application runs ---

    # Teardown
    logger.info("track-mcp API shutting down")
    from app.database import close_db as _close_db
    await _close_db(app)
    if app.state.redis:
        await app.state.redis.aclose()
    logger.info("track-mcp API shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI application instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="track-mcp",
    description="Motorsport telemetry analysis platform API",
    version="0.1.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    default_response_class=ORJSONResponse,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(sessions_router, prefix="/api/v1")
app.include_router(vehicles_router, prefix="/api/v1")
app.include_router(laps_router, prefix="/api/v1")
app.include_router(telemetry_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(coaching_router, prefix="/api/v1")
app.include_router(circuits_router, prefix="/api/v1")
app.include_router(corner_knowledge_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------

_raw_origins = os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173")
CORS_ORIGINS: list[str] = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------

@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    start = time.perf_counter()
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        "http_request",
        status_code=response.status_code,
        duration_ms=duration_ms,
    )
    response.headers["X-Response-Time-Ms"] = str(duration_ms)
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get(
    "/health",
    summary="Liveness probe",
    tags=["ops"],
    response_model=dict[str, Any],
)
async def health() -> dict[str, Any]:
    """
    Simple liveness probe. Returns 200 if the process is running.
    Used by Docker healthcheck and load balancers.
    """
    return {"status": "ok", "service": "track-mcp-api"}


@app.get(
    "/ready",
    summary="Readiness probe",
    tags=["ops"],
    response_model=dict[str, Any],
)
async def ready(request: Request) -> ORJSONResponse:
    """
    Readiness probe. Checks that the database and Redis are reachable.
    Returns 200 when all dependencies are up, 503 otherwise.
    """
    checks: dict[str, str] = {}
    overall_ok = True

    # --- Database ---
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool:
        try:
            async with db_pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"
            overall_ok = False
    else:
        checks["database"] = "unavailable"
        overall_ok = False

    # --- Redis ---
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client:
        try:
            await redis_client.ping()
            checks["redis"] = "ok"
        except Exception as exc:
            checks["redis"] = f"error: {exc}"
            overall_ok = False
    else:
        checks["redis"] = "unavailable"
        overall_ok = False

    uptime_s = round(time.time() - request.app.state.started_at, 1)

    body: dict[str, Any] = {
        "status": "ready" if overall_ok else "not_ready",
        "checks": checks,
        "uptime_seconds": uptime_s,
    }

    http_status = status.HTTP_200_OK if overall_ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return ORJSONResponse(content=body, status_code=http_status)


@app.get(
    "/api/v1/info",
    summary="API metadata",
    tags=["api"],
    response_model=dict[str, Any],
)
async def api_info() -> dict[str, Any]:
    """
    Returns basic metadata about the API version and enabled features.
    """
    return {
        "service": "track-mcp",
        "version": "0.1.0",
        "phase": "Phase 1 — schema + seed data",
        "environment": ENVIRONMENT,
        "features": {
            "ai_coaching": os.environ.get("ENABLE_AI_COACHING", "true").lower() == "true",
            "sector_analysis": os.environ.get("ENABLE_SECTOR_ANALYSIS", "true").lower() == "true",
        },
    }
