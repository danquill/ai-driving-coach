"""Pydantic v2 schemas for corner knowledge and insight feedback endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class CornerKnowledgeCreate(BaseModel):
    corner_number: Optional[int] = None
    typical_phase_of_interest: Optional[str] = None
    known_handling_tendency: Optional[str] = None
    correct_technique: Optional[str] = None
    incorrect_recommendations: Optional[list[str]] = None
    coaching_notes: Optional[str] = None
    source: str = "manual"


class CornerKnowledgeUpdate(BaseModel):
    corner_number: Optional[int] = None
    typical_phase_of_interest: Optional[str] = None
    known_handling_tendency: Optional[str] = None
    correct_technique: Optional[str] = None
    incorrect_recommendations: Optional[list[str]] = None
    coaching_notes: Optional[str] = None
    source: Optional[str] = None


class CornerKnowledgeResponse(BaseModel):
    id: uuid.UUID
    circuit_id: uuid.UUID
    corner_number: Optional[int] = None
    typical_phase_of_interest: Optional[str] = None
    known_handling_tendency: Optional[str] = None
    correct_technique: Optional[str] = None
    incorrect_recommendations: Optional[list[str]] = None
    coaching_notes: Optional[str] = None
    source: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class InsightFeedbackRequest(BaseModel):
    feedback: str  # 'good' | 'bad'
    feedback_note: Optional[str] = None
    auto_create_knowledge: bool = True


class InsightFeedbackResponse(BaseModel):
    insight_id: uuid.UUID
    feedback: str
    knowledge_id: Optional[uuid.UUID] = None
