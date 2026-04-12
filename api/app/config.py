"""Application configuration via Pydantic Settings.

Reads from environment variables and Docker secret files where applicable.
"""

from __future__ import annotations

import pathlib

from pydantic_settings import BaseSettings


def _read_secret_file(path: str) -> str | None:
    """Return the contents of a secret file if it exists, else None."""
    p = pathlib.Path(path)
    if p.exists():
        return p.read_text().strip()
    return None


class Settings(BaseSettings):
    # -------------------------------------------------------------------------
    # Database
    # -------------------------------------------------------------------------
    database_url: str = "postgresql+asyncpg://track:@db:5432/trackdb"

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = "redis://redis:6379/0"

    # -------------------------------------------------------------------------
    # JWT — prefer Docker secret file, fall back to env var
    # -------------------------------------------------------------------------
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # -------------------------------------------------------------------------
    # Beta mode — when True, registration requires a valid invite code
    # -------------------------------------------------------------------------
    beta_mode: bool = False

    # -------------------------------------------------------------------------
    # MinIO
    # -------------------------------------------------------------------------
    minio_endpoint: str = "minio:9000"
    minio_access_key: str = "trackminio"
    minio_secret_key: str = "changeme"
    minio_secure: bool = False

    def __init__(self, **values):
        # Resolve JWT secret from file if env var points to a file
        import os
        jwt_file = os.environ.get("JWT_SECRET_FILE")
        if jwt_file:
            secret = _read_secret_file(jwt_file)
            if secret:
                values.setdefault("jwt_secret", secret)
        else:
            # Try the well-known Docker secrets path
            secret = _read_secret_file("/run/secrets/jwt_secret")
            if secret:
                values.setdefault("jwt_secret", secret)

        # Resolve MinIO secret key from file
        minio_file = os.environ.get("MINIO_SECRET_KEY_FILE")
        if minio_file:
            minio_secret = _read_secret_file(minio_file)
            if minio_secret:
                values.setdefault("minio_secret_key", minio_secret)
        else:
            minio_secret = _read_secret_file("/run/secrets/minio_root_password")
            if minio_secret:
                values.setdefault("minio_secret_key", minio_secret)

        super().__init__(**values)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
