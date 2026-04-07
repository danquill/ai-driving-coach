"""Laps API endpoints — /sessions/{session_id}/laps."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.dependencies import get_current_user
from app.schemas.lap import IdealLapResponse, LapDetailResponse, LapSectorResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions/{session_id}/laps", tags=["laps"])


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


async def _fetch_lap_sectors(lap_id: uuid.UUID, db) -> list[LapSectorResponse]:
    rows = await db.fetch(
        """
        SELECT lap_id, sector_number, sector_time_ms, entry_speed_kph, exit_speed_kph
        FROM lap_sectors
        WHERE lap_id = $1
        ORDER BY sector_number
        """,
        lap_id,
    )
    return [
        LapSectorResponse(
            lap_id=r["lap_id"],
            sector_number=r["sector_number"],
            sector_time_ms=r["sector_time_ms"],
            entry_speed_kph=float(r["entry_speed_kph"]) if r["entry_speed_kph"] is not None else None,
            exit_speed_kph=float(r["exit_speed_kph"]) if r["exit_speed_kph"] is not None else None,
        )
        for r in rows
    ]


def _row_to_detail(row, sectors: list[LapSectorResponse]) -> LapDetailResponse:
    d = dict(row)
    return LapDetailResponse(
        id=d["id"],
        session_id=d["session_id"],
        lap_number=d["lap_number"],
        lap_time_ms=d.get("lap_time_ms"),
        is_outlap=d["is_outlap"],
        is_inlap=d["is_inlap"],
        is_valid=d["is_valid"],
        start_ts=d.get("start_ts"),
        end_ts=d.get("end_ts"),
        max_speed_kph=float(d["max_speed_kph"]) if d.get("max_speed_kph") is not None else None,
        min_speed_kph=float(d["min_speed_kph"]) if d.get("min_speed_kph") is not None else None,
        sectors=sectors,
    )


# ---------------------------------------------------------------------------
# Routes — IMPORTANT: /ideal must come BEFORE /{lap_number}
# ---------------------------------------------------------------------------

@router.get("/ideal", response_model=IdealLapResponse)
async def get_ideal_lap(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Return the latest theoretical ideal lap for this session."""
    await _get_session_or_404(session_id, current_user, db)

    row = await db.fetchrow(
        """
        SELECT id, session_id, theoretical_time_ms, sector_sources, constructed_at
        FROM ideal_laps
        WHERE session_id = $1
        ORDER BY constructed_at DESC
        LIMIT 1
        """,
        session_id,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No ideal lap found for this session")

    return IdealLapResponse(
        id=row["id"],
        session_id=row["session_id"],
        theoretical_time_ms=row["theoretical_time_ms"],
        sector_sources=row["sector_sources"],
        constructed_at=row["constructed_at"],
    )


@router.get("/", response_model=list[LapDetailResponse])
async def list_laps(
    session_id: uuid.UUID,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """List all laps with sector times for a session."""
    await _get_session_or_404(session_id, current_user, db)

    rows = await db.fetch(
        """
        SELECT id, session_id, lap_number, lap_time_ms, is_outlap, is_inlap,
               is_valid, start_ts, end_ts, max_speed_kph, min_speed_kph
        FROM laps
        WHERE session_id = $1
        ORDER BY lap_number
        """,
        session_id,
    )

    result = []
    for row in rows:
        sectors = await _fetch_lap_sectors(row["id"], db)
        result.append(_row_to_detail(row, sectors))

    return result


@router.get("/{lap_number}", response_model=LapDetailResponse)
async def get_lap(
    session_id: uuid.UUID,
    lap_number: int,
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get a single lap with sector details."""
    await _get_session_or_404(session_id, current_user, db)

    row = await db.fetchrow(
        """
        SELECT id, session_id, lap_number, lap_time_ms, is_outlap, is_inlap,
               is_valid, start_ts, end_ts, max_speed_kph, min_speed_kph
        FROM laps
        WHERE session_id = $1 AND lap_number = $2
        """,
        session_id,
        lap_number,
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lap not found")

    sectors = await _fetch_lap_sectors(row["id"], db)
    return _row_to_detail(row, sectors)
