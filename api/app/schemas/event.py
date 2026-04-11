"""Pydantic v2 schemas for event endpoints."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel


class CreateEventRequest(BaseModel):
    name: str
    event_date: Optional[date] = None
    circuit_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class UpdateEventRequest(BaseModel):
    name: Optional[str] = None
    event_date: Optional[date] = None
    circuit_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class AssignSessionsRequest(BaseModel):
    session_ids: list[uuid.UUID]


class EventResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    circuit_id: Optional[uuid.UUID] = None
    name: str
    event_date: Optional[date] = None
    notes: Optional[str] = None
    created_at: datetime
    circuit_name: Optional[str] = None

    model_config = {"from_attributes": True}
