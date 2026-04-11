"""FastAPI dependencies for authentication and authorisation."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.database import get_db
from app.services.auth import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db=Depends(get_db),
) -> dict:
    """Decode the JWT bearer token and fetch the matching active user from DB."""
    payload = decode_access_token(token)
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    row = await db.fetchrow(
        """
        SELECT id, email, display_name, role, created_at, is_active
        FROM users
        WHERE id = $1
        """,
        user_id,
    )

    if row is None or not row["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return dict(row)


async def require_admin(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require that the current user has the 'admin' role."""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


async def require_coach(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Require that the current user has the 'coach' or 'admin' role."""
    if current_user["role"] not in ("coach", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Coach privileges required",
        )
    return current_user
