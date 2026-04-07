"""Telemetry data API endpoints — /sessions/{session_id}/laps/{lap_number}/telemetry
and /sessions/{session_id}/telemetry/overlay."""

from __future__ import annotations

import uuid
from typing import Any, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import ORJSONResponse

from app.database import get_db
from app.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/sessions/{session_id}", tags=["telemetry"])

# Channels available in telemetry_samples (full resolution)
_FULL_CHANNELS = [
    "distance_m", "lat", "lon", "speed_kph", "throttle_pct", "brake_pct",
    "steering_deg", "gear", "rpm", "lat_g", "lon_g", "altitude_m",
    "heading_deg", "hdop", "satellites",
]

# Channels available in telemetry_samples_1hz (continuous aggregate)
_1HZ_CHANNELS = [
    "lat", "lon", "avg_speed_kph", "avg_throttle_pct", "avg_brake_pct",
    "avg_lat_g", "avg_lon_g",
]


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


# ---------------------------------------------------------------------------
# GET /laps/{lap_number}/telemetry
# ---------------------------------------------------------------------------

@router.get("/laps/{lap_number}/telemetry")
async def get_lap_telemetry(
    session_id: uuid.UUID,
    lap_number: int,
    channels: Optional[str] = Query(None, description="Comma-separated channel names"),
    resolution: str = Query("full", description="'full' or '1hz'"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ORJSONResponse:
    """
    Return telemetry data for a specific lap in columnar format.

    Always includes distance_m as the first channel (full resolution only).
    For 1hz resolution, distance_m is not available — lat/lon are included instead.
    """
    await _get_session_or_404(session_id, current_user, db)

    # Verify the lap exists
    lap_row = await db.fetchrow(
        "SELECT id FROM laps WHERE session_id = $1 AND lap_number = $2",
        session_id, lap_number,
    )
    if lap_row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lap not found")

    if resolution == "1hz":
        return await _get_telemetry_1hz(session_id, lap_number, channels, db)
    else:
        return await _get_telemetry_full(session_id, lap_number, channels, db)


async def _get_telemetry_full(
    session_id: uuid.UUID,
    lap_number: int,
    channels_param: Optional[str],
    db,
) -> ORJSONResponse:
    """Query telemetry_samples directly for full resolution data."""
    # Parse requested channels
    if channels_param:
        requested = [c.strip() for c in channels_param.split(",") if c.strip()]
        # Filter to valid channels (exclude distance_m — always included as first)
        valid_extra = [c for c in requested if c in _FULL_CHANNELS and c != "distance_m"]
    else:
        # Default: all channels except distance_m (it's always first)
        valid_extra = [c for c in _FULL_CHANNELS if c != "distance_m"]

    # Always include time and distance_m
    select_cols = ["time", "distance_m"] + valid_extra
    col_list = ", ".join(select_cols)

    rows = await db.fetch(
        f"""
        SELECT {col_list}
        FROM telemetry_samples
        WHERE session_id = $1 AND lap_number = $2
        ORDER BY time
        """,
        session_id,
        lap_number,
    )

    # Build columnar output: distance_m is always first data column
    channel_names = ["distance_m"] + valid_extra
    data = []
    for row in rows:
        row_data = []
        for col in ["distance_m"] + valid_extra:
            val = row[col]
            row_data.append(float(val) if val is not None else None)
        data.append(row_data)

    return ORJSONResponse({
        "lap_number": lap_number,
        "channels": channel_names,
        "data": data,
    })


async def _get_telemetry_1hz(
    session_id: uuid.UUID,
    lap_number: int,
    channels_param: Optional[str],
    db,
) -> ORJSONResponse:
    """Query telemetry_samples_1hz continuous aggregate for downsampled data."""
    if channels_param:
        requested = [c.strip() for c in channels_param.split(",") if c.strip()]
        valid_extra = [c for c in requested if c in _1HZ_CHANNELS]
    else:
        valid_extra = list(_1HZ_CHANNELS)

    select_cols = ["bucket"] + valid_extra
    col_list = ", ".join(select_cols)

    rows = await db.fetch(
        f"""
        SELECT {col_list}
        FROM telemetry_samples_1hz
        WHERE session_id = $1 AND lap_number = $2
        ORDER BY bucket
        """,
        session_id,
        lap_number,
    )

    channel_names = valid_extra
    data = []
    for row in rows:
        row_data = []
        for col in valid_extra:
            val = row[col]
            row_data.append(float(val) if val is not None else None)
        data.append(row_data)

    return ORJSONResponse({
        "lap_number": lap_number,
        "channels": channel_names,
        "data": data,
    })


# ---------------------------------------------------------------------------
# GET /telemetry/overlay
# ---------------------------------------------------------------------------

@router.get("/telemetry/overlay")
async def get_telemetry_overlay(
    session_id: uuid.UUID,
    laps: list[int] = Query(..., description="Lap numbers — repeat param for multiple, e.g. laps=1&laps=2"),
    channels: list[str] = Query(["speed_kph", "throttle_pct", "brake_pct"], description="Channel names — repeat param for multiple"),
    resolution: str = Query("full", description="'full' or '1hz'"),
    db=Depends(get_db),
    current_user: dict = Depends(get_current_user),
) -> ORJSONResponse:
    """
    Return distance-aligned multi-lap telemetry data.

    Data is keyed by distance_m (rounded to nearest meter) and interpolated
    to 1m intervals using linear interpolation between samples.
    """
    import numpy as np

    await _get_session_or_404(session_id, current_user, db)

    lap_numbers = laps
    if not lap_numbers:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one lap number required")

    # Filter to valid channels (distance_m handled separately)
    data_channels = [c for c in channels if c in _FULL_CHANNELS and c != "distance_m"]
    if not data_channels:
        data_channels = ["speed_kph", "throttle_pct", "brake_pct"]

    result_by_lap: dict[str, list[list[Any]]] = {}
    output_channels = ["distance_m"] + data_channels

    for lap_number in lap_numbers:
        # Fetch samples for this lap
        col_list = "distance_m, " + ", ".join(data_channels)
        rows = await db.fetch(
            f"""
            SELECT {col_list}
            FROM telemetry_samples
            WHERE session_id = $1 AND lap_number = $2
              AND distance_m IS NOT NULL
            ORDER BY distance_m
            """,
            session_id,
            lap_number,
        )

        if not rows:
            result_by_lap[str(lap_number)] = []
            continue

        # Extract distance and channel arrays
        dist_arr = np.array([float(r["distance_m"]) for r in rows], dtype=float)

        # Handle potential duplicate distances (take mean or just filter)
        if len(dist_arr) < 2:
            result_by_lap[str(lap_number)] = []
            continue

        max_dist = float(dist_arr[-1])
        min_dist = float(dist_arr[0])

        # 1m interpolation grid
        interp_distances = np.arange(round(min_dist), round(max_dist) + 1, 1.0)

        lap_data: list[list[Any]] = []
        channel_arrays: list[np.ndarray] = []

        for ch in data_channels:
            ch_vals = np.array([
                float(r[ch]) if r[ch] is not None else float("nan")
                for r in rows
            ], dtype=float)
            # Fill NaN with interpolated values where possible
            valid_mask = ~np.isnan(ch_vals)
            if valid_mask.sum() >= 2:
                # Interpolate using only valid samples
                interp_vals = np.interp(
                    interp_distances,
                    dist_arr[valid_mask],
                    ch_vals[valid_mask],
                )
            else:
                interp_vals = np.full(len(interp_distances), float("nan"))
            channel_arrays.append(interp_vals)

        # Build columnar output: [distance_m, ch1, ch2, ...]
        for i, d in enumerate(interp_distances):
            row_vals: list[Any] = [round(float(d), 1)]
            for ch_arr in channel_arrays:
                v = ch_arr[i]
                row_vals.append(None if np.isnan(v) else round(float(v), 4))
            lap_data.append(row_vals)

        result_by_lap[str(lap_number)] = lap_data

    return ORJSONResponse({
        "channels": output_channels,
        "laps": result_by_lap,
    })
