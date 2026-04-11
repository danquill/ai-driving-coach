"""Pydantic v2 schemas for session endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


SESSION_TYPES = {"hpde", "practice", "qualifying", "race", "test"}


class CreateSessionRequest(BaseModel):
    name: Optional[str] = None
    session_date: Optional[date] = None
    vehicle_id: Optional[uuid.UUID] = None
    circuit_id: Optional[uuid.UUID] = None
    ambient_temp_c: Optional[float] = None
    notes: Optional[str] = None
    session_type: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    name: Optional[str] = None
    session_date: Optional[date] = None
    vehicle_id: Optional[uuid.UUID] = None
    circuit_id: Optional[uuid.UUID] = None
    ambient_temp_c: Optional[float] = None
    notes: Optional[str] = None
    session_type: Optional[str] = None


class SessionResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    vehicle_id: Optional[uuid.UUID] = None
    circuit_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    session_date: Optional[date] = None
    ambient_temp_c: Optional[float] = None
    notes: Optional[str] = None
    session_type: Optional[str] = None
    status: str
    created_at: datetime
    best_lap_time_ms: Optional[int] = None
    circuit_name: Optional[str] = None

    model_config = {"from_attributes": True}
