"""Dataclass representations of the users and refresh_tokens DB tables.

These mirror the raw asyncpg Row objects returned by parameterised queries.
No SQLAlchemy ORM is used anywhere in this module.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class User:
    id: uuid.UUID
    email: str
    password_hash: str
    display_name: str
    created_at: datetime
    is_active: bool
    role: str  # 'driver' | 'coach' | 'admin'


@dataclass
class RefreshToken:
    id: uuid.UUID
    user_id: uuid.UUID
    token_hash: str
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime]
    device_hint: Optional[str]
