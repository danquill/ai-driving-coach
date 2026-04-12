"""Auth routes: register, login, refresh, logout."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from app.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.services.auth import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


async def _issue_token_pair(user_id: str, role: str, db: asyncpg.Connection) -> TokenResponse:
    """Create a new access+refresh token pair and persist the refresh token."""
    access_token = create_access_token(user_id=user_id, role=role)
    refresh_token = create_refresh_token()
    token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)

    await db.execute(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
        VALUES ($1, $2, $3)
        """,
        user_id,
        token_hash,
        expires_at,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.get("/beta-status")
async def beta_status() -> dict:
    """Return whether beta mode is active (public endpoint)."""
    return {"beta_mode": settings.beta_mode}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db=Depends(get_db)) -> TokenResponse:
    """Create a new user account and return a token pair."""
    # Beta mode: require a valid, unused invite code
    invite_row = None
    if settings.beta_mode:
        if not body.invite_code:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="beta_mode: an invite code is required to register",
            )
        invite_row = await db.fetchrow(
            """
            SELECT id, email FROM invite_codes
            WHERE code = $1 AND used_at IS NULL
            """,
            body.invite_code,
        )
        if invite_row is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or already-used invite code",
            )
        # If the code was locked to a specific email, enforce it
        if invite_row["email"] and invite_row["email"].lower() != body.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This invite code is not valid for that email address",
            )

    # Check for existing email
    existing = await db.fetchval(
        "SELECT id FROM users WHERE email = $1",
        body.email,
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    password_hash = hash_password(body.password)

    row = await db.fetchrow(
        """
        INSERT INTO users (email, password_hash, display_name)
        VALUES ($1, $2, $3)
        RETURNING id, role
        """,
        body.email,
        password_hash,
        body.display_name,
    )

    # Mark invite as used
    if invite_row is not None:
        await db.execute(
            "UPDATE invite_codes SET used_at = now(), used_by = $1 WHERE id = $2",
            row["id"],
            invite_row["id"],
        )

    return await _issue_token_pair(str(row["id"]), row["role"], db)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db=Depends(get_db)) -> TokenResponse:
    """Authenticate with email + password and return a token pair."""
    row = await db.fetchrow(
        "SELECT id, password_hash, role, is_active FROM users WHERE email = $1",
        body.email,
    )

    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await _issue_token_pair(str(row["id"]), row["role"], db)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, db=Depends(get_db)) -> TokenResponse:
    """Rotate a refresh token and return a new token pair."""
    token_hash = hash_refresh_token(body.refresh_token)

    row = await db.fetchrow(
        """
        SELECT id, user_id
        FROM refresh_tokens
        WHERE token_hash = $1
          AND revoked_at IS NULL
          AND expires_at > now()
        """,
        token_hash,
    )

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Revoke the old token
    await db.execute(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE id = $1",
        row["id"],
    )

    # Fetch user role for the new access token
    user_row = await db.fetchrow(
        "SELECT role FROM users WHERE id = $1",
        row["user_id"],
    )

    return await _issue_token_pair(str(row["user_id"]), user_row["role"], db)


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(body: RefreshRequest, db=Depends(get_db)) -> dict:
    """Revoke the supplied refresh token."""
    token_hash = hash_refresh_token(body.refresh_token)

    await db.execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = $1 AND revoked_at IS NULL
        """,
        token_hash,
    )
    # Always return 200 — don't reveal whether the token existed
    return {"detail": "Logged out successfully"}
