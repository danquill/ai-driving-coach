"""
track-mcp Celery application — Phase 0/1 stub.

Defines the Celery app instance and task queues.
Individual task modules will be added in subsequent phases:
  - tasks/parse.py       — telemetry file parsing
  - tasks/lap_detect.py  — lap boundary detection
  - tasks/sectors.py     — sector time analysis
  - tasks/ideal_lap.py   — theoretical best lap construction
  - tasks/ai_coaching.py — Anthropic AI coaching insights
"""

from __future__ import annotations

import os
import pathlib

import structlog
from celery import Celery
from celery.signals import (
    worker_ready,
    worker_shutdown,
    task_prerun,
    task_postrun,
    task_failure,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

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
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Secret helpers
# ---------------------------------------------------------------------------

def _read_secret(env_var: str, default: str = "") -> str:
    """Return value from Docker secret file or env var fallback."""
    file_path = os.environ.get(f"{env_var}_FILE")
    if file_path:
        p = pathlib.Path(file_path)
        if p.exists():
            return p.read_text().strip()
    return os.environ.get(env_var, default)


# ---------------------------------------------------------------------------
# Build broker / backend URLs
# ---------------------------------------------------------------------------

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

# ---------------------------------------------------------------------------
# Celery application
# ---------------------------------------------------------------------------

app = Celery(
    "track_mcp",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # Timezone
    timezone="UTC",
    enable_utc=True,
    # Task execution
    task_acks_late=True,           # Acknowledge only after task completes
    task_reject_on_worker_lost=True,  # Requeue if worker dies mid-task
    worker_prefetch_multiplier=1,  # One task at a time per worker thread
    # Result retention
    result_expires=86400,          # Keep results for 24 hours
    # Retries
    task_max_retries=3,
    task_default_retry_delay=30,   # seconds
    # Queues
    task_default_queue="default",
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "parse": {
            "exchange": "parse",
            "routing_key": "parse",
        },
        "analysis": {
            "exchange": "analysis",
            "routing_key": "analysis",
        },
    },
    # Routing: route specific task types to specific queues
    task_routes={
        "worker.app.tasks.parse.*": {"queue": "parse"},
        "worker.app.tasks.lap_detect.*": {"queue": "parse"},
        "worker.app.tasks.sectors.*": {"queue": "analysis"},
        "worker.app.tasks.ideal_lap.*": {"queue": "analysis"},
        "worker.app.tasks.ai_coaching.*": {"queue": "analysis"},
    },
    # Beat schedule (placeholder — populate in later phases)
    beat_schedule={},
    # Flower / monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# ---------------------------------------------------------------------------
# Auto-discover task modules
# ---------------------------------------------------------------------------
app.autodiscover_tasks([
    "worker.app.tasks.parse",
    "worker.app.tasks.lap_detect",
    "worker.app.tasks.sector_analysis",
    "worker.app.tasks.ideal_lap",
    "worker.app.tasks.ai_coaching",
])


# ---------------------------------------------------------------------------
# Stub tasks — placeholders that will be replaced in later phases
# ---------------------------------------------------------------------------

@app.task(
    name="app.tasks.lap_detect.detect_laps",
    bind=True,
    queue="parse",
    max_retries=3,
    default_retry_delay=15,
)
def detect_laps(self, session_id: str) -> dict:
    """
    Detect lap boundaries from telemetry_samples using the circuit's
    start/finish coordinates and geofence. Stub — not yet implemented.
    """
    logger.info(
        "detect_laps stub called",
        session_id=session_id,
        task_id=self.request.id,
    )
    raise NotImplementedError("detect_laps is not yet implemented")


@app.task(
    name="app.tasks.sectors.analyse_sectors",
    bind=True,
    queue="analysis",
    max_retries=3,
    default_retry_delay=30,
)
def analyse_sectors(self, session_id: str) -> dict:
    """
    Compute sector times, entry/exit speeds, and braking events for all
    valid laps in a session. Stub — not yet implemented.
    """
    logger.info(
        "analyse_sectors stub called",
        session_id=session_id,
        task_id=self.request.id,
    )
    raise NotImplementedError("analyse_sectors is not yet implemented")


@app.task(
    name="app.tasks.ideal_lap.construct_ideal_lap",
    bind=True,
    queue="analysis",
    max_retries=2,
    default_retry_delay=30,
)
def construct_ideal_lap(self, session_id: str) -> dict:
    """
    Construct a theoretical best lap by combining the fastest sector from
    each recorded lap in the session. Stub — not yet implemented.
    """
    logger.info(
        "construct_ideal_lap stub called",
        session_id=session_id,
        task_id=self.request.id,
    )
    raise NotImplementedError("construct_ideal_lap is not yet implemented")


@app.task(
    name="app.tasks.ai_coaching.generate_coaching_insights",
    bind=True,
    queue="analysis",
    max_retries=2,
    default_retry_delay=60,
)
def generate_coaching_insights(
    self,
    session_id: str,
    analysis_job_id: str,
    lap_ids: list[str] | None = None,
) -> dict:
    """
    Call the Anthropic API to generate AI coaching insights for a session.
    Writes results to the coaching_insights table. Stub — not yet implemented.
    """
    logger.info(
        "generate_coaching_insights stub called",
        session_id=session_id,
        analysis_job_id=analysis_job_id,
        task_id=self.request.id,
    )
    raise NotImplementedError("generate_coaching_insights is not yet implemented")


# ---------------------------------------------------------------------------
# Signal handlers
# ---------------------------------------------------------------------------

@worker_ready.connect
def on_worker_ready(sender=None, **kwargs) -> None:
    logger.info("Celery worker ready", hostname=sender.hostname if sender else "unknown")


@worker_shutdown.connect
def on_worker_shutdown(sender=None, **kwargs) -> None:
    logger.info("Celery worker shutting down")


@task_prerun.connect
def on_task_prerun(task_id=None, task=None, args=None, kwargs=None, **extra) -> None:
    structlog.contextvars.bind_contextvars(
        task_id=task_id,
        task_name=task.name if task else "unknown",
    )
    logger.info("task_started")


@task_postrun.connect
def on_task_postrun(task_id=None, task=None, state=None, **extra) -> None:
    logger.info("task_finished", state=state)
    structlog.contextvars.clear_contextvars()


@task_failure.connect
def on_task_failure(task_id=None, exception=None, traceback=None, **extra) -> None:
    logger.error(
        "task_failed",
        task_id=task_id,
        error=str(exception),
    )
    structlog.contextvars.clear_contextvars()
