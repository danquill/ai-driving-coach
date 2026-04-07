"""parse_telemetry_file Celery task — Phase 3."""

from __future__ import annotations

import os
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import structlog

# ---------------------------------------------------------------------------
# Path setup: make the shared api/app package importable from the worker
# ---------------------------------------------------------------------------
# The Dockerfile copies api/app into /app/api/app inside the worker container.
# We add /app/api to sys.path so that `from app.adapters import ...` resolves.

_API_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api")
_API_SRC = os.path.abspath(_API_SRC)
if _API_SRC not in sys.path:
    sys.path.insert(0, _API_SRC)

# Also try env-override path
_API_SRC_ENV = os.environ.get("API_SRC_PATH")
if _API_SRC_ENV and _API_SRC_ENV not in sys.path:
    sys.path.insert(0, _API_SRC_ENV)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# DB connection helper (sync psycopg2)
# ---------------------------------------------------------------------------

def _get_sync_db_conn():
    """Return a psycopg2 connection using SYNC_DATABASE_URL with secret injection."""
    import psycopg2

    dsn = os.environ.get(
        "SYNC_DATABASE_URL",
        "postgresql://track:DOCKER-SECRET@db:5432/trackdb",
    )

    # Inject password from Docker secret file if available
    password = ""
    secret_path = pathlib.Path("/run/secrets/db_password")
    if secret_path.exists():
        password = secret_path.read_text().strip()
    else:
        pw_file = os.environ.get("DB_PASSWORD_FILE")
        if pw_file:
            p = pathlib.Path(pw_file)
            if p.exists():
                password = p.read_text().strip()
        if not password:
            password = os.environ.get("DB_PASSWORD", "")

    dsn = dsn.replace("DOCKER-SECRET", password)
    return psycopg2.connect(dsn)


# ---------------------------------------------------------------------------
# MinIO helper (sync)
# ---------------------------------------------------------------------------

def _get_storage():
    """Return a Minio client configured from environment."""
    import pathlib as _pl
    from minio import Minio

    endpoint = os.environ.get("MINIO_ENDPOINT", "minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "trackminio")

    # Secret key from Docker secret
    secret_key = ""
    sk_file_path = os.environ.get("MINIO_SECRET_KEY_FILE")
    if sk_file_path:
        p = _pl.Path(sk_file_path)
        if p.exists():
            secret_key = p.read_text().strip()
    if not secret_key:
        p = _pl.Path("/run/secrets/minio_root_password")
        if p.exists():
            secret_key = p.read_text().strip()
    if not secret_key:
        secret_key = os.environ.get("MINIO_SECRET_KEY", "changeme")

    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"
    return Minio(endpoint=endpoint, access_key=access_key, secret_key=secret_key, secure=secure)


# ---------------------------------------------------------------------------
# Batch insert helper
# ---------------------------------------------------------------------------

_BATCH_SIZE = 1000

_INSERT_SQL = """
    INSERT INTO telemetry_samples (
        time, session_id, lap_number, distance_m, lat, lon,
        speed_kph, throttle_pct, brake_pct, steering_deg,
        gear, rpm, lat_g, lon_g, altitude_m, heading_deg,
        hdop, satellites
    ) VALUES %s
    ON CONFLICT DO NOTHING
"""


def _frames_to_rows(frames, session_id: str, base_time: datetime):
    """Convert TelemetryFrame objects to DB row tuples."""
    rows = []
    for f in frames:
        if f.wall_time is not None:
            ts = f.wall_time
        else:
            ts = base_time + timedelta(milliseconds=f.timestamp_ms)

        rows.append((
            ts,
            session_id,
            f.lap_number,
            f.distance_m,
            f.lat,
            f.lon,
            f.speed_kph,
            f.throttle_pct,
            f.brake_pct,
            f.steering_deg,
            f.gear,
            f.rpm,
            f.lat_g,
            f.lon_g,
            f.altitude_m,
            f.heading_deg,
            f.hdop,
            f.satellites,
        ))
    return rows


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

from worker.app.celery_app import app as celery_app  # noqa: E402


@celery_app.task(
    name="worker.app.tasks.parse.parse_telemetry_file",
    bind=True,
    queue="parse",
    max_retries=3,
    default_retry_delay=15,
)
def parse_telemetry_file(
    self,
    session_id: str,
    raw_file_id: str,
    job_id: str,
    storage_key: str,
) -> dict:
    """
    Parse a raw telemetry file and insert samples into telemetry_samples.

    Args:
        session_id:    UUID string of the session.
        raw_file_id:   UUID string of the raw_files record.
        job_id:        UUID string of the analysis_jobs record.
        storage_key:   MinIO object key (e.g. {session_id}/{raw_file_id}/{filename}).
    """
    logger.info(
        "parse_task_started",
        session_id=session_id,
        raw_file_id=raw_file_id,
        job_id=job_id,
        storage_key=storage_key,
    )

    conn = None
    try:
        from psycopg2.extras import execute_values

        conn = _get_sync_db_conn()
        cur = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Update job status → running
        # ------------------------------------------------------------------
        cur.execute(
            """
            UPDATE analysis_jobs
            SET status = 'running', started_at = now()
            WHERE id = %s
            """,
            (job_id,),
        )
        conn.commit()

        # ------------------------------------------------------------------
        # 2. Download file from MinIO
        # ------------------------------------------------------------------
        minio_client = _get_storage()
        RAW_BUCKET = "raw-files"

        response = minio_client.get_object(bucket_name=RAW_BUCKET, object_name=storage_key)
        try:
            file_bytes = response.read()
        finally:
            response.close()
            response.release_conn()

        logger.info("parse_task_downloaded", bytes=len(file_bytes))

        # ------------------------------------------------------------------
        # 3. Resolve adapter
        # ------------------------------------------------------------------
        from app.adapters import resolve_adapter  # type: ignore

        filename = storage_key.split("/")[-1]
        adapter = resolve_adapter(file_bytes, filename)
        logger.info("parse_task_adapter", adapter=adapter.FORMAT_ID)

        # ------------------------------------------------------------------
        # 4. Parse frames
        # ------------------------------------------------------------------
        frames = list(adapter.parse(file_bytes))
        logger.info("parse_task_frames_raw", count=len(frames))

        # ------------------------------------------------------------------
        # 5. Validate frames
        # ------------------------------------------------------------------
        from app.services.validation import validate_frames  # type: ignore

        frames = validate_frames(frames)
        logger.info("parse_task_frames_validated", count=len(frames))

        # ------------------------------------------------------------------
        # 6. Fetch session base time for wall_time synthesis
        # ------------------------------------------------------------------
        cur.execute("SELECT created_at FROM sessions WHERE id = %s", (session_id,))
        session_row = cur.fetchone()
        base_time = session_row[0] if session_row else datetime.now(timezone.utc)
        if base_time.tzinfo is None:
            base_time = base_time.replace(tzinfo=timezone.utc)

        # ------------------------------------------------------------------
        # 7. Update session status → processing
        # ------------------------------------------------------------------
        cur.execute(
            "UPDATE sessions SET status = 'processing' WHERE id = %s",
            (session_id,),
        )
        conn.commit()

        # ------------------------------------------------------------------
        # 8. Batch insert telemetry_samples
        # ------------------------------------------------------------------
        all_rows = _frames_to_rows(frames, session_id, base_time)
        total_inserted = 0

        for batch_start in range(0, len(all_rows), _BATCH_SIZE):
            batch = all_rows[batch_start: batch_start + _BATCH_SIZE]
            execute_values(cur, _INSERT_SQL, batch)
            conn.commit()
            total_inserted += len(batch)
            logger.info("parse_task_batch_inserted", batch_size=len(batch), total=total_inserted)

        # ------------------------------------------------------------------
        # 9. Update job → done
        # ------------------------------------------------------------------
        import json

        result_summary = json.dumps({"frame_count": len(frames), "inserted": total_inserted})
        cur.execute(
            """
            UPDATE analysis_jobs
            SET status = 'done',
                completed_at = now(),
                result_summary = %s::jsonb
            WHERE id = %s
            """,
            (result_summary, job_id),
        )
        conn.commit()

        logger.info(
            "parse_task_completed",
            session_id=session_id,
            frames=len(frames),
            inserted=total_inserted,
        )

        # ------------------------------------------------------------------
        # 10. Auto-dispatch lap_detect task
        # ------------------------------------------------------------------
        try:
            import uuid as _uuid
            detect_job_id = str(_uuid.uuid4())
            # Get session owner for requested_by (NOT NULL constraint)
            cur.execute("SELECT owner_id FROM sessions WHERE id = %s", (session_id,))
            owner_row = cur.fetchone()
            owner_id = str(owner_row[0]) if owner_row else None
            if owner_id:
                cur.execute(
                    """
                    INSERT INTO analysis_jobs
                        (id, session_id, requested_by, job_type, status)
                    VALUES (%s, %s, %s, 'lap_detect', 'queued')
                    """,
                    (detect_job_id, session_id, owner_id),
                )
                conn.commit()
                from worker.app.tasks.lap_detect import detect_laps_task
                detect_laps_task.apply_async(
                    args=[session_id, detect_job_id],
                    queue="parse",
                )
                logger.info("parse_task_dispatched_lap_detect", detect_job_id=detect_job_id)
        except Exception as dispatch_exc:
            logger.error("parse_task_dispatch_failed", error=str(dispatch_exc))

        return {"frame_count": len(frames), "inserted": total_inserted}

    except Exception as exc:
        logger.error("parse_task_failed", error=str(exc), session_id=session_id, job_id=job_id)
        if conn:
            try:
                conn.rollback()
                cur2 = conn.cursor()
                cur2.execute(
                    """
                    UPDATE analysis_jobs
                    SET status = 'failed', error_message = %s, completed_at = now()
                    WHERE id = %s
                    """,
                    (str(exc)[:2000], job_id),
                )
                conn.commit()
            except Exception:
                pass
        raise

    finally:
        if conn:
            conn.close()
