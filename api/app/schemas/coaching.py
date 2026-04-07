"""Pydantic v2 schemas for coaching insight endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CoachingInsightResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    lap_id: Optional[uuid.UUID] = None
    analysis_job_id: uuid.UUID
    category: str
    insight_text: str
    confidence: Optional[float] = None
    distance_m_start: Optional[float] = None
    distance_m_end: Optional[float] = None
    model_version: Optional[str] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}
