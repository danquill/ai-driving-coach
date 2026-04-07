"""Pydantic v2 schemas for vehicle endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CreateVehicleRequest(BaseModel):
    make: str
    model: str
    year: Optional[int] = None
    class_: Optional[str] = Field(default=None, alias="class")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class UpdateVehicleRequest(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    class_: Optional[str] = Field(default=None, alias="class")
    notes: Optional[str] = None

    model_config = {"populate_by_name": True}


class VehicleResponse(BaseModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    make: str
    model: str
    year: Optional[int] = None
    class_: Optional[str] = Field(default=None, alias="class")
    notes: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
