"""
Alembic environment configuration for track-mcp.

Uses a synchronous psycopg2-style URL (SYNC_DATABASE_URL) for migrations.
The password is read from the Docker secret file at runtime so that no
credentials appear in environment variables or config files.
"""

import os
import pathlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Interpret the config file for Python logging if present
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Build the database URL at runtime
# ---------------------------------------------------------------------------

def _read_secret(env_var: str, default: str | None = None) -> str | None:
    """
    Read a value from a Docker secret file if <env_var>_FILE is set,
    otherwise fall back to the plain environment variable.
    """
    file_path = os.environ.get(f"{env_var}_FILE")
    if file_path:
        p = pathlib.Path(file_path)
        if p.exists():
            return p.read_text().strip()
    return os.environ.get(env_var, default)


def _build_sync_url() -> str:
    """
    Construct a synchronous PostgreSQL URL for Alembic.
    Priority:
      1. SYNC_DATABASE_URL env var (must not contain the real password)
      2. Assemble from parts
    """
    # Allow a fully pre-assembled URL (password placeholder replaced)
    base_url = os.environ.get("SYNC_DATABASE_URL", "")
    db_password = _read_secret("DB_PASSWORD")

    if base_url and db_password:
        # Replace the placeholder used in docker-compose
        url = base_url.replace("DOCKER-SECRET", db_password)
        # Ensure we use psycopg2 (sync) driver
        url = url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
        return url

    # Fallback: assemble from individual parts
    host = os.environ.get("DB_HOST", "db")
    port = os.environ.get("DB_PORT", "5432")
    user = os.environ.get("DB_USER", "track")
    dbname = os.environ.get("DB_NAME", "trackdb")
    password = db_password or ""
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{dbname}"


# Inject the URL into Alembic's config so engine_from_config picks it up
config.set_main_option("sqlalchemy.url", _build_sync_url())

# We are not using declarative metadata — all DDL is raw SQL via op.execute()
target_metadata = None


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL script, no connection)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (direct DB connection)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
