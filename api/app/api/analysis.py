"""Analysis jobs API endpoints — /sessions/{session_id}/analyze and /jobs."""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions/{session_id}", tags=["analysis"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    job_type: str  # 'lap_detect' | 'sector_analysis' | 'ideal_lap'
    params: Optional[dict] = None


class JobResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    job_type: str
    status: str
    error_message: Optional[str] = None
    result_summary: Optional[Any] = None
    queued_at: Any
    started_at: Optional[Any] = None
    completed_at: Optional[Any] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Helper: verify session ownership
# ---------------------------------------------------------------------------

async def _get_session_or_404(session_id: uuid.UUID, current_user: dict, db) -> dict:
    row = await db.fetchrow(
        "SELECT * FROM sessions WHERE id = $1 AND status != 'deleted'",
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    if str(row["owner_id"]) != str(current_user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return dict(row)


def _row_to_job(row) -> JobResponse:
    d = dict(row)
    return JobResponse(**d)


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------

_VALID_JOB_TYPES = {"lap_detect", "sector_analysis", "ideal_lap", "ai_coaching"}


@router.post("/analyze", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    session_id: uuid.UUID,
    body: AnalyzeRequest,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger an analysis job for this session."""
    session = await _get_session_or_404(session_id, current_user, db)

    if body.job_type not in _VALID_JOB_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid job_type. Must be one of: {', '.join(sorted(_VALID_JOB_TYPES))}",
        )

    # For lap_detect: verify circuit is assigned
    if body.job_type == "lap_detect":
        if session.get("circuit_id") is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No circuit assigned to this session. Assign a circuit before running lap detection.",
            )

    # For ai_coaching: verify an ideal_lap exists and compare_lap_number is provided
    if body.job_type == "ai_coaching":
        ideal_row = await db.fetchrow(
            "SELECT id FROM ideal_laps WHERE session_id = $1 LIMIT 1",
            session_id,
        )
        if ideal_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Complete sector analysis before requesting coaching insights",
            )
        if not (body.params or {}).get("compare_lap_number"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Select a lap to analyse before generating insights",
            )

    job_id = uuid.uuid4()
    await db.execute(
        """
        INSERT INTO analysis_jobs
            (id, session_id, requested_by, job_type, status, input_params)
        VALUES ($1, $2, $3, $4, 'queued', $5)
        """,
        job_id,
        session_id,
        uuid.UUID(str(current_user["id"])),
        body.job_type,
        json.dumps(body.params or {}),
    )

    # Dispatch the appropriate Celery task
    from app.celery_client import celery_app

    task_map = {
        "lap_detect": "worker.app.tasks.lap_detect.detect_laps_task",
        "sector_analysis": "worker.app.tasks.sector_analysis.sector_analysis_task",
        "ideal_lap": "worker.app.tasks.ideal_lap.ideal_lap_task",
        "ai_coaching": "worker.app.tasks.ai_coaching.generate_coaching_insights_task",
    }
    queue_map = {
        "lap_detect": "parse",
        "sector_analysis": "analysis",
        "ideal_lap": "analysis",
        "ai_coaching": "analysis",
    }

    task_name = task_map[body.job_type]
    queue = queue_map[body.job_type]

    celery_app.send_task(
        task_name,
        args=[str(session_id), str(job_id)],
        task_id=str(job_id),
        queue=queue,
    )

    logger.info(
        "analysis_job_queued",
        session_id=str(session_id),
        job_id=str(job_id),
        job_type=body.job_type,
    )

    return {"job_id": str(job_id), "job_type": body.job_type, "status": "queued"}


# ---------------------------------------------------------------------------
# GET /jobs
# ---------------------------------------------------------------------------

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all analysis jobs for a session, ordered by queued_at desc."""
    await _get_session_or_404(session_id, current_user, db)

    rows = await db.fetch(
        """
        SELECT id, session_id, job_type, status, error_message, result_summary,
               queued_at, started_at, completed_at
        FROM analysis_jobs
        WHERE session_id = $1
        ORDER BY queued_at DESC
        """,
        session_id,
    )
    return [_row_to_job(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /jobs/{job_id}
# ---------------------------------------------------------------------------

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(
    session_id: uuid.UUID,
    job_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a specific analysis job by ID."""
    await _get_session_or_404(session_id, current_user, db)

    row = await db.fetchrow(
        """
        SELECT id, session_id, job_type, status, error_message, result_summary,
               queued_at, started_at, completed_at
        FROM analysis_jobs
        WHERE id = $1 AND session_id = $2
        """,
        job_id,
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return _row_to_job(row)
