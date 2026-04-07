"""Initial schema — relational tables + TimescaleDB hypertable + continuous aggregate.

Revision ID: 001
Revises:
Create Date: 2026-04-04 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# ---------------------------------------------------------------------------
# Revision identifiers
# ---------------------------------------------------------------------------
revision: str = "001"
down_revision: str | None = None
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:
    # -----------------------------------------------------------------------
    # 0. Extensions
    # -----------------------------------------------------------------------
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE')

    # -----------------------------------------------------------------------
    # 1. users
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE users (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            display_name    TEXT NOT NULL,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            is_active       BOOLEAN NOT NULL DEFAULT true,
            role            TEXT NOT NULL DEFAULT 'driver'
                                CHECK (role IN ('driver', 'coach', 'admin'))
        )
    """)

    op.execute("CREATE INDEX idx_users_email ON users (email)")
    op.execute("CREATE INDEX idx_users_role ON users (role)")

    # -----------------------------------------------------------------------
    # 2. refresh_tokens
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE refresh_tokens (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            token_hash  TEXT UNIQUE NOT NULL,
            issued_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at  TIMESTAMPTZ NOT NULL,
            revoked_at  TIMESTAMPTZ,
            device_hint TEXT
        )
    """)

    op.execute("CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id)")
    op.execute("CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens (expires_at)")

    # -----------------------------------------------------------------------
    # 3. vehicles
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE vehicles (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id    UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            make        TEXT NOT NULL,
            model       TEXT NOT NULL,
            year        SMALLINT,
            class       TEXT,
            notes       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_vehicles_owner_id ON vehicles (owner_id)")

    # -----------------------------------------------------------------------
    # 4. circuits
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE circuits (
            id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name                        TEXT NOT NULL,
            country                     TEXT,
            timezone                    TEXT NOT NULL DEFAULT 'UTC',
            start_finish_lat            DOUBLE PRECISION,
            start_finish_lon            DOUBLE PRECISION,
            start_finish_heading_deg    NUMERIC(6,2),
            geofence_radius_m           NUMERIC(8,2),
            track_length_m              NUMERIC(10,2),
            geometry                    GEOMETRY(LineString, 4326),
            created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_circuits_name ON circuits (name)")
    op.execute("CREATE INDEX idx_circuits_geometry ON circuits USING GIST (geometry)")

    # -----------------------------------------------------------------------
    # 5. circuit_sectors
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE circuit_sectors (
            id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            circuit_id              UUID NOT NULL REFERENCES circuits (id) ON DELETE CASCADE,
            sector_number           SMALLINT NOT NULL,
            trigger_lat             DOUBLE PRECISION NOT NULL,
            trigger_lon             DOUBLE PRECISION NOT NULL,
            trigger_heading_deg     NUMERIC(6,2),
            UNIQUE (circuit_id, sector_number)
        )
    """)

    op.execute("CREATE INDEX idx_circuit_sectors_circuit_id ON circuit_sectors (circuit_id)")

    # -----------------------------------------------------------------------
    # 6. sessions
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE sessions (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            owner_id        UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            vehicle_id      UUID REFERENCES vehicles (id) ON DELETE SET NULL,
            circuit_id      UUID REFERENCES circuits (id) ON DELETE SET NULL,
            name            TEXT,
            session_date    DATE,
            ambient_temp_c  NUMERIC(5,2),
            notes           TEXT,
            status          TEXT NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'processing', 'ready', 'failed', 'ready_no_laps', 'deleted')),
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_sessions_owner_id ON sessions (owner_id)")
    op.execute("CREATE INDEX idx_sessions_circuit_id ON sessions (circuit_id)")
    op.execute("CREATE INDEX idx_sessions_vehicle_id ON sessions (vehicle_id)")
    op.execute("CREATE INDEX idx_sessions_status ON sessions (status)")
    op.execute("CREATE INDEX idx_sessions_session_date ON sessions (session_date DESC)")

    # -----------------------------------------------------------------------
    # 7. session_shares (scaffold only — no API endpoints in Phase 1)
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE session_shares (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id      UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            shared_with     UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            granted_by      UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            permission      TEXT NOT NULL DEFAULT 'read'
                                CHECK (permission IN ('read', 'comment')),
            granted_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            revoked_at      TIMESTAMPTZ,
            UNIQUE (session_id, shared_with)
        )
    """)

    op.execute("CREATE INDEX idx_session_shares_session_id ON session_shares (session_id)")
    op.execute("CREATE INDEX idx_session_shares_shared_with ON session_shares (shared_with)")

    # -----------------------------------------------------------------------
    # 8. raw_files
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE raw_files (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id          UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            original_filename   TEXT NOT NULL,
            storage_key         TEXT UNIQUE NOT NULL,
            file_format         TEXT NOT NULL
                                    CHECK (file_format IN ('vbo', 'drk', 'xdrk', 'ld', 'csv')),
            file_size_bytes     BIGINT,
            sha256              TEXT,
            uploaded_at         TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_raw_files_session_id ON raw_files (session_id)")
    op.execute("CREATE INDEX idx_raw_files_sha256 ON raw_files (sha256)")

    # -----------------------------------------------------------------------
    # 9. laps
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE laps (
            id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id      UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            lap_number      SMALLINT NOT NULL,
            lap_time_ms     INTEGER,
            is_outlap       BOOLEAN NOT NULL DEFAULT false,
            is_inlap        BOOLEAN NOT NULL DEFAULT false,
            is_valid        BOOLEAN NOT NULL DEFAULT true,
            start_ts        TIMESTAMPTZ,
            end_ts          TIMESTAMPTZ,
            max_speed_kph   NUMERIC(7,2),
            min_speed_kph   NUMERIC(7,2),
            UNIQUE (session_id, lap_number)
        )
    """)

    op.execute("CREATE INDEX idx_laps_session_id ON laps (session_id)")
    op.execute("CREATE INDEX idx_laps_is_valid ON laps (session_id, is_valid) WHERE is_valid = true")

    # -----------------------------------------------------------------------
    # 10. lap_sectors
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE lap_sectors (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            lap_id              UUID NOT NULL REFERENCES laps (id) ON DELETE CASCADE,
            circuit_sector_id   UUID NOT NULL REFERENCES circuit_sectors (id) ON DELETE CASCADE,
            sector_number       SMALLINT NOT NULL,
            sector_time_ms      INTEGER NOT NULL,
            entry_speed_kph     NUMERIC(7,2),
            exit_speed_kph      NUMERIC(7,2),
            UNIQUE (lap_id, sector_number)
        )
    """)

    op.execute("CREATE INDEX idx_lap_sectors_lap_id ON lap_sectors (lap_id)")
    op.execute("CREATE INDEX idx_lap_sectors_circuit_sector_id ON lap_sectors (circuit_sector_id)")

    # -----------------------------------------------------------------------
    # 11. braking_events
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE braking_events (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            lap_id              UUID NOT NULL REFERENCES laps (id) ON DELETE CASCADE,
            distance_m          NUMERIC(10,2),
            brake_start_pct     NUMERIC(5,2),
            peak_brake_pct      NUMERIC(5,2),
            duration_ms         INTEGER,
            speed_at_brake_kph  NUMERIC(7,2)
        )
    """)

    op.execute("CREATE INDEX idx_braking_events_lap_id ON braking_events (lap_id)")
    op.execute("CREATE INDEX idx_braking_events_distance ON braking_events (lap_id, distance_m)")

    # -----------------------------------------------------------------------
    # 12. ideal_laps
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE ideal_laps (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id          UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            constructed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            theoretical_time_ms INTEGER NOT NULL,
            sector_sources      JSONB NOT NULL
        )
    """)

    op.execute("CREATE INDEX idx_ideal_laps_session_id ON ideal_laps (session_id)")

    # -----------------------------------------------------------------------
    # 13. analysis_jobs
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE analysis_jobs (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id          UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            requested_by        UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            job_type            TEXT NOT NULL
                                    CHECK (job_type IN (
                                        'parse', 'lap_detect', 'sector_analysis',
                                        'ideal_lap', 'ai_coaching'
                                    )),
            celery_task_id      TEXT UNIQUE,
            status              TEXT NOT NULL DEFAULT 'queued'
                                    CHECK (status IN (
                                        'queued', 'running', 'done', 'failed', 'retrying'
                                    )),
            error_message       TEXT,
            input_params        JSONB,
            result_summary      JSONB,
            queued_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at          TIMESTAMPTZ,
            completed_at        TIMESTAMPTZ,
            notify_on_complete  BOOLEAN NOT NULL DEFAULT false
        )
    """)

    op.execute("CREATE INDEX idx_analysis_jobs_session_id ON analysis_jobs (session_id)")
    op.execute("CREATE INDEX idx_analysis_jobs_requested_by ON analysis_jobs (requested_by)")
    op.execute("CREATE INDEX idx_analysis_jobs_status ON analysis_jobs (status)")
    op.execute("CREATE INDEX idx_analysis_jobs_celery_task_id ON analysis_jobs (celery_task_id)")

    # -----------------------------------------------------------------------
    # 14. coaching_insights
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE coaching_insights (
            id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            session_id          UUID NOT NULL REFERENCES sessions (id) ON DELETE CASCADE,
            lap_id              UUID REFERENCES laps (id) ON DELETE SET NULL,
            analysis_job_id     UUID NOT NULL REFERENCES analysis_jobs (id) ON DELETE CASCADE,
            category            TEXT NOT NULL
                                    CHECK (category IN (
                                        'braking', 'corner_entry', 'corner_exit',
                                        'sector', 'general'
                                    )),
            insight_text        TEXT NOT NULL,
            confidence          NUMERIC(3,2),
            distance_m_start    NUMERIC(10,2),
            distance_m_end      NUMERIC(10,2),
            model_version       TEXT,
            prompt_tokens       INTEGER,
            completion_tokens   INTEGER,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("CREATE INDEX idx_coaching_insights_session_id ON coaching_insights (session_id)")
    op.execute("CREATE INDEX idx_coaching_insights_lap_id ON coaching_insights (lap_id)")
    op.execute("CREATE INDEX idx_coaching_insights_analysis_job_id ON coaching_insights (analysis_job_id)")
    op.execute("CREATE INDEX idx_coaching_insights_category ON coaching_insights (category)")

    # -----------------------------------------------------------------------
    # 15. telemetry_samples — TimescaleDB hypertable
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE TABLE telemetry_samples (
            time            TIMESTAMPTZ NOT NULL,
            session_id      UUID NOT NULL,
            lap_number      SMALLINT,
            distance_m      DOUBLE PRECISION,
            lat             DOUBLE PRECISION,
            lon             DOUBLE PRECISION,
            speed_kph       NUMERIC(8,3),
            throttle_pct    NUMERIC(5,2),
            brake_pct       NUMERIC(5,2),
            steering_deg    NUMERIC(7,3),
            gear            SMALLINT,
            rpm             INTEGER,
            lat_g           NUMERIC(7,4),
            lon_g           NUMERIC(7,4),
            altitude_m      NUMERIC(8,3),
            heading_deg     NUMERIC(6,3),
            hdop            NUMERIC(5,2),
            satellites      SMALLINT
        )
    """)

    # Convert to a TimescaleDB hypertable partitioned on `time`
    op.execute("""
        SELECT create_hypertable(
            'telemetry_samples',
            'time',
            chunk_time_interval => INTERVAL '1 day',
            if_not_exists => TRUE
        )
    """)

    # Recommended: add session_id as a space partition dimension
    # (improves performance for per-session queries across large datasets)
    op.execute("""
        SELECT add_dimension(
            'telemetry_samples',
            'session_id',
            number_partitions => 4,
            if_not_exists => TRUE
        )
    """)

    # Indexes on the hypertable
    op.execute("""
        CREATE INDEX idx_telemetry_session_time
            ON telemetry_samples (session_id, time DESC)
    """)

    op.execute("""
        CREATE INDEX idx_telemetry_session_lap_distance
            ON telemetry_samples (session_id, lap_number, distance_m)
    """)

    # -----------------------------------------------------------------------
    # 16. Continuous aggregate — 1-second bucketed telemetry
    # -----------------------------------------------------------------------
    op.execute("""
        CREATE MATERIALIZED VIEW telemetry_samples_1hz
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 second', time)   AS bucket,
            session_id,
            lap_number,
            AVG(speed_kph)                  AS avg_speed_kph,
            AVG(throttle_pct)               AS avg_throttle_pct,
            AVG(brake_pct)                  AS avg_brake_pct,
            AVG(lat_g)                      AS avg_lat_g,
            AVG(lon_g)                      AS avg_lon_g,
            first(lat, time)                AS lat,
            first(lon, time)                AS lon
        FROM telemetry_samples
        GROUP BY bucket, session_id, lap_number
        WITH NO DATA
    """)

    # Refresh policy: keep the 1hz aggregate up to date automatically
    op.execute("""
        SELECT add_continuous_aggregate_policy(
            'telemetry_samples_1hz',
            start_offset  => INTERVAL '3 days',
            end_offset    => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE
        )
    """)

    # Compression policy on the raw hypertable (compress chunks older than 7 days)
    op.execute("""
        ALTER TABLE telemetry_samples SET (
            timescaledb.compress,
            timescaledb.compress_orderby = 'time DESC',
            timescaledb.compress_segmentby = 'session_id'
        )
    """)

    op.execute("""
        SELECT add_compression_policy(
            'telemetry_samples',
            INTERVAL '7 days',
            if_not_exists => TRUE
        )
    """)


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------

def downgrade() -> None:
    # Drop in reverse dependency order

    # Continuous aggregate + compression policy
    op.execute("DROP MATERIALIZED VIEW IF EXISTS telemetry_samples_1hz CASCADE")

    # Hypertable (and its policies)
    op.execute("DROP TABLE IF EXISTS telemetry_samples CASCADE")

    # Relational tables
    op.execute("DROP TABLE IF EXISTS coaching_insights CASCADE")
    op.execute("DROP TABLE IF EXISTS analysis_jobs CASCADE")
    op.execute("DROP TABLE IF EXISTS ideal_laps CASCADE")
    op.execute("DROP TABLE IF EXISTS braking_events CASCADE")
    op.execute("DROP TABLE IF EXISTS lap_sectors CASCADE")
    op.execute("DROP TABLE IF EXISTS laps CASCADE")
    op.execute("DROP TABLE IF EXISTS raw_files CASCADE")
    op.execute("DROP TABLE IF EXISTS session_shares CASCADE")
    op.execute("DROP TABLE IF EXISTS sessions CASCADE")
    op.execute("DROP TABLE IF EXISTS circuit_sectors CASCADE")
    op.execute("DROP TABLE IF EXISTS circuits CASCADE")
    op.execute("DROP TABLE IF EXISTS vehicles CASCADE")
    op.execute("DROP TABLE IF EXISTS refresh_tokens CASCADE")
    op.execute("DROP TABLE IF EXISTS users CASCADE")

    # Extensions (leave timescaledb — it may affect other DBs in the cluster)
    op.execute("DROP EXTENSION IF EXISTS postgis CASCADE")
    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp" CASCADE')
