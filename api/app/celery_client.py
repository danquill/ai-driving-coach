"""Minimal Celery client used by the API container to dispatch tasks.

The API does not import the full worker module — it only needs to send tasks
to the broker. This module provides a lightweight Celery app configured with
the same broker/backend as the worker.
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "track_mcp_client",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
