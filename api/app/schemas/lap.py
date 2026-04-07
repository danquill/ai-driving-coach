"""Pydantic v2 schemas for lap endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class LapSectorResponse(BaseModel):
    lap_id: uuid.UUID
    sector_number: int
    sector_time_ms: int
    entry_speed_kph: Optional[float] = None
    exit_speed_kph: Optional[float] = None

    model_config = {"from_attributes": True}


class LapResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    lap_number: int
    lap_time_ms: Optional[int] = None
    is_outlap: bool
    is_inlap: bool
    is_valid: bool
    start_ts: Optional[datetime] = None
    end_ts: Optional[datetime] = None
    max_speed_kph: Optional[float] = None
    min_speed_kph: Optional[float] = None

    model_config = {"from_attributes": True}


class LapDetailResponse(LapResponse):
    sectors: list[LapSectorResponse] = []


class IdealLapResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    theoretical_time_ms: int
    sector_sources: Any  # JSONB — list of {sector_number, lap_id, sector_time_ms}
    constructed_at: datetime

    model_config = {"from_attributes": True}
