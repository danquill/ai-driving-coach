"""detect_laps_task — Celery task for GPS-based lap boundary detection."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid
from datetime import datetime, timezone

import structlog

# ---------------------------------------------------------------------------
# Path setup: make the shared api/app package importable from the worker
# ---------------------------------------------------------------------------
_API_SRC = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api")
_API_SRC = os.path.abspath(_API_SRC)
if _API_SRC not in sys.path:
    sys.path.insert(0, _API_SRC)

_API_SRC_ENV = os.environ.get("API_SRC_PATH")
if _API_SRC_ENV and _API_SRC_ENV not in sys.path:
    sys.path.insert(0, _API_SRC_ENV)

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# DB helper (sync psycopg2) — reused from parse.py pattern
# ---------------------------------------------------------------------------

def _get_sync_db_conn():
    import psycopg2

    dsn = os.environ.get(
        "SYNC_DATABASE_URL",
        "postgresql://track:DOCKER-SECRET@db:5432/trackdb",
    )
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
# Celery task
# ---------------------------------------------------------------------------

from worker.app.celery_app import app as celery_app  # noqa: E402


@celery_app.task(
    name="worker.app.tasks.lap_detect.detect_laps_task",
    bind=True,
    queue="parse",
    max_retries=3,
    default_retry_delay=15,
)
def detect_laps_task(self, session_id: str, job_id: str) -> dict:
    """
    Detect lap boundaries for a session using GPS haversine + heading algorithm.
    After completion, dispatches sector_analysis_task automatically.
    """
    logger.info("lap_detect_task_started", session_id=session_id, job_id=job_id)

    conn = None
    try:
        from psycopg2.extras import execute_values, RealDictCursor

        conn = _get_sync_db_conn()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # ------------------------------------------------------------------
        # 1. Update job → running
        # ------------------------------------------------------------------
        conn.cursor().execute(
            "UPDATE analysis_jobs SET status = 'running', started_at = now() WHERE id = %s",
            (job_id,),
        )
        conn.commit()

        # ------------------------------------------------------------------
        # 2. Fetch circuit for the session
        # ------------------------------------------------------------------
        plain_cur = conn.cursor()
        plain_cur.execute(
            """
            SELECT c.id, c.start_finish_lat, c.start_finish_lon,
                   c.start_finish_heading_deg, c.geofence_radius_m
            FROM sessions s
            JOIN circuits c ON c.id = s.circuit_id
            WHERE s.id = %s
            """,
            (session_id,),
        )
        circuit_row = plain_cur.fetchone()
        if circuit_row is None:
            plain_cur.execute(
                """
                UPDATE analysis_jobs
                SET status = 'failed',
                    error_message = 'No circuit assigned to session',
                    completed_at = now()
                WHERE id = %s
                """,
                (job_id,),
            )
            conn.commit()
            logger.warning("lap_detect_no_circuit", session_id=session_id)
            return {"error": "No circuit assigned to session"}

        circuit = {
            "id": str(circuit_row[0]),
            "start_finish_lat": circuit_row[1],
            "start_finish_lon": circuit_row[2],
            "start_finish_heading_deg": circuit_row[3],
            "geofence_radius_m": circuit_row[4],
        }

        # ------------------------------------------------------------------
        # 3. Stream telemetry samples via named cursor
        # ------------------------------------------------------------------
        samples = []
        with conn.cursor("stream_cursor") as stream_cur:
            stream_cur.itersize = 2000
            stream_cur.execute(
                """
                SELECT time, lat, lon, speed_kph, heading_deg, distance_m
                FROM telemetry_samples
                WHERE session_id = %s
                ORDER BY time
                """,
                (session_id,),
            )
            for row in stream_cur:
                samples.append({
                    "time": row[0],
                    "lat": float(row[1]) if row[1] is not None else None,
                    "lon": float(row[2]) if row[2] is not None else None,
                    "speed_kph": float(row[3]) if row[3] is not None else None,
                    "heading_deg": float(row[4]) if row[4] is not None else None,
                    "distance_m": float(row[5]) if row[5] is not None else None,
                })

        logger.info("lap_detect_samples_loaded", count=len(samples))

        if not samples:
            plain_cur.execute(
                """
                UPDATE analysis_jobs
                SET status = 'done', completed_at = now(),
                    result_summary = %s::jsonb
                WHERE id = %s
                """,
                (json.dumps({"lap_count": 0, "message": "No telemetry samples"}), job_id),
            )
            conn.commit()
            return {"lap_count": 0}

        # ------------------------------------------------------------------
        # 4. Call detect_laps()
        # ------------------------------------------------------------------
        from app.services.lap_detection import detect_laps, assign_lap_numbers  # type: ignore

        laps = detect_laps(samples, circuit)
        logger.info("lap_detect_laps_found", count=len(laps))

        # ------------------------------------------------------------------
        # 5. Assign lap numbers to samples
        # ------------------------------------------------------------------
        samples = assign_lap_numbers(samples, laps)

        # ------------------------------------------------------------------
        # 6. Batch UPDATE telemetry_samples.lap_number
        # ------------------------------------------------------------------
        if laps:
            lap_ranges = [
                (lap["lap_number"], lap["start_time"], lap["end_time"])
                for lap in laps
            ]
            update_cur = conn.cursor()
            for lap_number, start_time, end_time in lap_ranges:
                update_cur.execute(
                    """
                    UPDATE telemetry_samples
                    SET lap_number = %s
                    WHERE session_id = %s
                      AND time >= %s
                      AND time < %s
                    """,
                    (lap_number, session_id, start_time, end_time),
                )
            conn.commit()
            logger.info("lap_detect_lap_numbers_updated")

        # ------------------------------------------------------------------
        # 7. Compute max/min speed per lap from tagged samples
        # ------------------------------------------------------------------
        lap_speeds: dict[int, tuple[float, float]] = {}  # lap_number -> (max, min)
        for s in samples:
            ln = s.get("lap_number")
            spd = s.get("speed_kph")
            if ln is None or spd is None:
                continue
            if ln not in lap_speeds:
                lap_speeds[ln] = (spd, spd)
            else:
                cur_max, cur_min = lap_speeds[ln]
                lap_speeds[ln] = (max(cur_max, spd), min(cur_min, spd))

        # ------------------------------------------------------------------
        # 8. INSERT lap records into laps table
        # ------------------------------------------------------------------
        if laps:
            insert_cur = conn.cursor()
            for lap in laps:
                ln = lap["lap_number"]
                max_spd = lap_speeds[ln][0] if ln in lap_speeds else None
                min_spd = lap_speeds[ln][1] if ln in lap_speeds else None
                insert_cur.execute(
                    """
                    INSERT INTO laps
                        (session_id, lap_number, lap_time_ms, is_outlap, is_inlap,
                         is_valid, start_ts, end_ts, max_speed_kph, min_speed_kph)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (session_id, lap_number) DO UPDATE
                        SET lap_time_ms    = EXCLUDED.lap_time_ms,
                            is_outlap      = EXCLUDED.is_outlap,
                            is_inlap       = EXCLUDED.is_inlap,
                            is_valid       = EXCLUDED.is_valid,
                            start_ts       = EXCLUDED.start_ts,
                            end_ts         = EXCLUDED.end_ts,
                            max_speed_kph  = EXCLUDED.max_speed_kph,
                            min_speed_kph  = EXCLUDED.min_speed_kph
                    """,
                    (
                        session_id,
                        ln,
                        lap["lap_time_ms"],
                        lap["is_outlap"],
                        lap["is_inlap"],
                        not (lap["is_outlap"] or lap["is_inlap"]),
                        lap["start_time"],
                        lap["end_time"],
                        max_spd,
                        min_spd,
                    ),
                )
            conn.commit()
            logger.info("lap_detect_laps_inserted", count=len(laps))

        # ------------------------------------------------------------------
        # 9. Update job → done
        # ------------------------------------------------------------------
        valid_laps = [l for l in laps if not l["is_outlap"] and not l["is_inlap"]]
        result = {
            "lap_count": len(laps),
            "valid_lap_count": len(valid_laps),
        }
        plain_cur.execute(
            """
            UPDATE analysis_jobs
            SET status = 'done', completed_at = now(), result_summary = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(result), job_id),
        )
        conn.commit()

        logger.info("lap_detect_task_completed", session_id=session_id, **result)

        # ------------------------------------------------------------------
        # 10. Dispatch sector_analysis_task automatically
        # ------------------------------------------------------------------
        _dispatch_sector_analysis(conn, session_id)

        return result

    except Exception as exc:
        logger.error("lap_detect_task_failed", error=str(exc), session_id=session_id)
        if conn:
            try:
                conn.rollback()
                err_cur = conn.cursor()
                err_cur.execute(
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


def _dispatch_sector_analysis(conn, session_id: str) -> None:
    """Create a sector_analysis job and dispatch the Celery task."""
    try:
        # Get session owner for requested_by
        cur = conn.cursor()
        cur.execute("SELECT owner_id FROM sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        if row is None:
            logger.warning("lap_detect_dispatch_no_session", session_id=session_id)
            return
        owner_id = str(row[0])

        new_job_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO analysis_jobs
                (id, session_id, requested_by, job_type, status)
            VALUES (%s, %s, %s, 'sector_analysis', 'queued')
            """,
            (new_job_id, session_id, owner_id),
        )
        conn.commit()

        from worker.app.tasks.sector_analysis import sector_analysis_task
        sector_analysis_task.apply_async(
            args=[session_id, new_job_id],
            queue="analysis",
        )
        logger.info("lap_detect_dispatched_sector_analysis", job_id=new_job_id)
    except Exception as exc:
        logger.error("lap_detect_dispatch_failed", error=str(exc))
