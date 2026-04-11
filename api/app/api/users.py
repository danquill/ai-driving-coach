"""User routes: GET /me, PATCH /me, and admin user management."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.dependencies import get_current_user, require_admin
from app.schemas.user import UpdateUserRequest, UserResponse
from app.services.auth import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


class AdminUpdateUserRequest(BaseModel):
    role: Optional[str] = None
    is_active: Optional[bool] = None


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    """Return the profile of the currently authenticated user."""
    return UserResponse(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user["display_name"],
        role=current_user["role"],
        created_at=current_user["created_at"],
    )


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UpdateUserRequest,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
) -> UserResponse:
    """Update the current user's display_name and/or password."""

    # If requesting a password change, verify current_password first
    if body.new_password is not None:
        if body.current_password is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="current_password is required to set a new password",
            )
        # Fetch the password hash from DB (current_user dict doesn't include it)
        row = await db.fetchrow(
            "SELECT password_hash FROM users WHERE id = $1",
            current_user["id"],
        )
        if not verify_password(body.current_password, row["password_hash"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect",
            )

    # Build update fields dynamically
    fields: list[str] = []
    values: list = []
    idx = 1

    if body.display_name is not None:
        fields.append(f"display_name = ${idx}")
        values.append(body.display_name)
        idx += 1

    if body.new_password is not None:
        fields.append(f"password_hash = ${idx}")
        values.append(hash_password(body.new_password))
        idx += 1

    if not fields:
        # Nothing to update — return current state
        return UserResponse(
            id=current_user["id"],
            email=current_user["email"],
            display_name=current_user["display_name"],
            role=current_user["role"],
            created_at=current_user["created_at"],
        )

    values.append(current_user["id"])
    query = f"""
        UPDATE users
        SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING id, email, display_name, role, created_at
    """

    updated = await db.fetchrow(query, *values)
    return UserResponse(
        id=updated["id"],
        email=updated["email"],
        display_name=updated["display_name"],
        role=updated["role"],
        created_at=updated["created_at"],
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[UserResponse])
async def list_users(
    _admin: dict = Depends(require_admin),
    db=Depends(get_db),
) -> list[UserResponse]:
    """List all users. Admin only."""
    rows = await db.fetch(
        "SELECT id, email, display_name, role, is_active, created_at FROM users ORDER BY created_at DESC"
    )
    return [UserResponse(**dict(r)) for r in rows]


@router.patch("/{user_id}", response_model=UserResponse)
async def admin_update_user(
    user_id: uuid.UUID,
    body: AdminUpdateUserRequest,
    current_admin: dict = Depends(require_admin),
    db=Depends(get_db),
) -> UserResponse:
    """Update a user's role or active status. Admin only."""
    _VALID_ROLES = {"driver", "coach", "admin"}
    if body.role is not None and body.role not in _VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Must be one of: {', '.join(sorted(_VALID_ROLES))}",
        )

    # Prevent admin from demoting themselves
    if str(user_id) == str(current_admin["id"]) and body.role is not None and body.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own admin role",
        )

    fields: list[str] = []
    values: list = []
    idx = 1

    if body.role is not None:
        fields.append(f"role = ${idx}")
        values.append(body.role)
        idx += 1

    if body.is_active is not None:
        fields.append(f"is_active = ${idx}")
        values.append(body.is_active)
        idx += 1

    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No fields to update")

    values.append(user_id)
    query = f"""
        UPDATE users SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING id, email, display_name, role, is_active, created_at
    """
    row = await db.fetchrow(query, *values)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserResponse(**dict(row))
