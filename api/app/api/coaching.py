"""Coaching insights API endpoints.

Router prefix: /sessions/{session_id}

Endpoints:
  GET /insights                      — list all coaching insights for a session
  GET /laps/{lap_number}/insights    — insights relevant to a specific lap
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.dependencies import get_current_user, require_coach
from app.schemas.coaching import CoachingInsightResponse
from app.schemas.knowledge import InsightFeedbackRequest, InsightFeedbackResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions/{session_id}", tags=["coaching"])


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


def _row_to_insight(row) -> CoachingInsightResponse:
    return CoachingInsightResponse(**dict(row))


# ---------------------------------------------------------------------------
# GET /insights
# ---------------------------------------------------------------------------

@router.get("/insights", response_model=list[CoachingInsightResponse])
async def list_coaching_insights(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all coaching insights for a session, ordered by created_at desc."""
    await _get_session_or_404(session_id, current_user, db)

    rows = await db.fetch(
        """
        SELECT id, session_id, lap_id, lap_number, analysis_job_id, category, insight_text,
               confidence, distance_m_start, distance_m_end, model_version,
               prompt_tokens, completion_tokens, created_at, feedback, feedback_note
        FROM coaching_insights
        WHERE session_id = $1
        ORDER BY created_at DESC
        """,
        session_id,
    )
    return [_row_to_insight(r) for r in rows]


# ---------------------------------------------------------------------------
# GET /laps/{lap_number}/insights
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DELETE /insights/{insight_id}
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DELETE /insights  (delete all for session) — must be registered before /{insight_id}
# ---------------------------------------------------------------------------

@router.delete("/insights", status_code=204)
async def delete_all_coaching_insights(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete all coaching insights for a session."""
    await _get_session_or_404(session_id, current_user, db)
    await db.execute(
        "DELETE FROM coaching_insights WHERE session_id = $1",
        session_id,
    )


@router.delete("/insights/{insight_id}", status_code=204)
async def delete_coaching_insight(
    session_id: uuid.UUID,
    insight_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Delete a single coaching insight."""
    await _get_session_or_404(session_id, current_user, db)
    result = await db.execute(
        "DELETE FROM coaching_insights WHERE id = $1 AND session_id = $2",
        insight_id,
        session_id,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")


@router.get("/laps/{lap_number}/insights", response_model=list[CoachingInsightResponse])
async def list_lap_coaching_insights(
    session_id: uuid.UUID,
    lap_number: int,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List coaching insights relevant to a specific lap.

    Returns insights where lap_id matches the lap, or session-level insights
    (lap_id IS NULL) as a best-effort approximation when insights are session-wide.
    """
    await _get_session_or_404(session_id, current_user, db)

    # Resolve lap_id from lap_number
    lap_row = await db.fetchrow(
        "SELECT id FROM laps WHERE session_id = $1 AND lap_number = $2",
        session_id,
        lap_number,
    )
    if lap_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lap {lap_number} not found for this session",
        )
    lap_id = lap_row["id"]

    # Return insights tied to this lap OR session-level insights (lap_id IS NULL)
    rows = await db.fetch(
        """
        SELECT id, session_id, lap_id, lap_number, analysis_job_id, category, insight_text,
               confidence, distance_m_start, distance_m_end, model_version,
               prompt_tokens, completion_tokens, created_at, feedback, feedback_note
        FROM coaching_insights
        WHERE session_id = $1
          AND (lap_id = $2 OR lap_id IS NULL)
        ORDER BY created_at DESC
        """,
        session_id,
        lap_id,
    )
    return [_row_to_insight(r) for r in rows]


# ---------------------------------------------------------------------------
# POST /insights/{insight_id}/feedback
# ---------------------------------------------------------------------------

@router.post("/insights/{insight_id}/feedback", response_model=InsightFeedbackResponse)
async def submit_insight_feedback(
    session_id: uuid.UUID,
    insight_id: uuid.UUID,
    body: InsightFeedbackRequest,
    db=Depends(get_db),
    current_user: dict = Depends(require_coach),
):
    """Submit good/bad feedback on a coaching insight.

    When feedback is 'bad' and feedback_note is provided, optionally auto-creates
    a circuit_corner_knowledge entry from the correction note.
    """
    if body.feedback not in ("good", "bad"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="feedback must be 'good' or 'bad'",
        )

    session = await _get_session_or_404(session_id, current_user, db)

    insight_row = await db.fetchrow(
        "SELECT id, distance_m_start FROM coaching_insights WHERE id = $1 AND session_id = $2",
        insight_id,
        session_id,
    )
    if insight_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Insight not found")

    await db.execute(
        "UPDATE coaching_insights SET feedback = $1, feedback_note = $2 WHERE id = $3",
        body.feedback,
        body.feedback_note,
        insight_id,
    )

    knowledge_id: uuid.UUID | None = None

    if body.feedback == "bad" and body.feedback_note and body.auto_create_knowledge:
        circuit_id = session.get("circuit_id")
        if circuit_id:
            distance_m = insight_row["distance_m_start"]
            corner_number: int | None = None
            if distance_m is not None:
                cn_row = await db.fetchrow(
                    """
                    SELECT corner_number FROM circuit_corners
                    WHERE circuit_id = $1
                    ORDER BY ABS(distance_m - $2)
                    LIMIT 1
                    """,
                    circuit_id,
                    float(distance_m),
                )
                if cn_row:
                    corner_number = cn_row["corner_number"]

            knowledge_row = await db.fetchrow(
                """
                INSERT INTO circuit_corner_knowledge
                    (circuit_id, corner_number, coaching_notes, source)
                VALUES ($1, $2, $3, 'correction')
                RETURNING id
                """,
                circuit_id,
                corner_number,
                body.feedback_note,
            )
            if knowledge_row:
                knowledge_id = knowledge_row["id"]

    return InsightFeedbackResponse(
        insight_id=insight_id,
        feedback=body.feedback,
        knowledge_id=knowledge_id,
    )
