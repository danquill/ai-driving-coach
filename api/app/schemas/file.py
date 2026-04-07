"""Pydantic v2 schemas for file upload endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class RawFileResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    original_filename: str
    file_format: str
    file_size_bytes: int | None
    uploaded_at: datetime

    model_config = {"from_attributes": True}


class UploadResponse(BaseModel):
    raw_file_id: uuid.UUID
    session_id: uuid.UUID
    job_id: uuid.UUID
    message: str
