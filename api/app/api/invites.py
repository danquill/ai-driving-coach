"""Invite code management — admin only."""

from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.database import get_db
from app.dependencies import get_current_user, require_admin

router = APIRouter(prefix="/invites", tags=["invites"])


class CreateInviteRequest(BaseModel):
    email: str | None = None  # optional — lock the code to a specific email


class InviteResponse(BaseModel):
    id: uuid.UUID
    code: str
    email: str | None
    used_at: str | None
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def create_invite(
    body: CreateInviteRequest,
    db=Depends(get_db),
    _admin=Depends(require_admin),
    current_user: dict = Depends(get_current_user),
):
    """Generate a new invite code (admin only)."""
    code = secrets.token_urlsafe(12)
    row = await db.fetchrow(
        """
        INSERT INTO invite_codes (code, email, created_by)
        VALUES ($1, $2, $3)
        RETURNING id, code, email, used_at, created_at
        """,
        code,
        body.email,
        current_user["id"],
    )
    return InviteResponse(
        id=row["id"],
        code=row["code"],
        email=row["email"],
        used_at=row["used_at"].isoformat() if row["used_at"] else None,
        created_at=row["created_at"].isoformat(),
    )


@router.get("/", response_model=list[InviteResponse])
async def list_invites(
    db=Depends(get_db),
    _admin=Depends(require_admin),
):
    """List all invite codes (admin only)."""
    rows = await db.fetch(
        "SELECT id, code, email, used_at, created_at FROM invite_codes ORDER BY created_at DESC"
    )
    return [
        InviteResponse(
            id=r["id"],
            code=r["code"],
            email=r["email"],
            used_at=r["used_at"].isoformat() if r["used_at"] else None,
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


@router.delete("/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invite(
    invite_id: uuid.UUID,
    db=Depends(get_db),
    _admin=Depends(require_admin),
):
    """Delete an unused invite code (admin only)."""
    row = await db.fetchrow(
        "SELECT id, used_at FROM invite_codes WHERE id = $1", invite_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Invite not found")
    if row["used_at"] is not None:
        raise HTTPException(status_code=400, detail="Cannot delete a used invite code")
    await db.execute("DELETE FROM invite_codes WHERE id = $1", invite_id)
