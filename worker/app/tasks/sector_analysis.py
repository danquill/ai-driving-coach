"""sector_analysis_task — Celery task for sector crossing detection and timing."""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid

import structlog

# ---------------------------------------------------------------------------
# Path setup
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
# DB helper
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
    name="worker.app.tasks.sector_analysis.sector_analysis_task",
    bind=True,
    queue="analysis",
    max_retries=3,
    default_retry_delay=30,
)
def sector_analysis_task(self, session_id: str, job_id: str) -> dict:
    """
    Compute sector times, entry/exit speeds for all valid laps in a session.
    Dispatches ideal_lap_task on completion.
    """
    logger.info("sector_analysis_task_started", session_id=session_id, job_id=job_id)

    conn = None
    try:
        conn = _get_sync_db_conn()
        cur = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Update job → running
        # ------------------------------------------------------------------
        cur.execute(
            "UPDATE analysis_jobs SET status = 'running', started_at = now() WHERE id = %s",
            (job_id,),
        )
        conn.commit()

        # ------------------------------------------------------------------
        # 2. Fetch all valid laps for the session
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT id, session_id, lap_number, lap_time_ms, is_outlap, is_inlap,
                   is_valid, start_ts, end_ts
            FROM laps
            WHERE session_id = %s
              AND is_outlap = false
              AND is_inlap = false
              AND is_valid = true
            ORDER BY lap_number
            """,
            (session_id,),
        )
        lap_rows = cur.fetchall()
        laps = [
            {
                "id": str(row[0]),
                "session_id": str(row[1]),
                "lap_number": row[2],
                "lap_time_ms": row[3],
                "is_outlap": row[4],
                "is_inlap": row[5],
                "is_valid": row[6],
                "start_ts": row[7],
                "end_ts": row[8],
            }
            for row in lap_rows
        ]
        logger.info("sector_analysis_laps_loaded", count=len(laps))

        # ------------------------------------------------------------------
        # 3. Fetch circuit_sectors for the session's circuit
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT cs.id, cs.sector_number, cs.trigger_lat, cs.trigger_lon,
                   cs.trigger_heading_deg
            FROM circuit_sectors cs
            JOIN sessions s ON s.circuit_id = cs.circuit_id
            WHERE s.id = %s
            ORDER BY cs.sector_number
            """,
            (session_id,),
        )
        sector_rows = cur.fetchall()
        sectors = [
            {
                "id": str(row[0]),
                "sector_number": row[1],
                "trigger_lat": float(row[2]),
                "trigger_lon": float(row[3]),
                "trigger_heading_deg": float(row[4]) if row[4] is not None else None,
            }
            for row in sector_rows
        ]
        logger.info("sector_analysis_sectors_loaded", count=len(sectors))

        # ------------------------------------------------------------------
        # 4. Process each valid lap
        # ------------------------------------------------------------------
        from app.services.sector_analysis import detect_sector_crossings, compute_sector_times  # type: ignore

        laps_processed = 0
        for lap in laps:
            lap_id = lap["id"]
            lap_number = lap["lap_number"]
            start_ts = lap["start_ts"]
            end_ts = lap["end_ts"]
            lap_time_ms = lap["lap_time_ms"]

            if start_ts is None or end_ts is None:
                logger.warning("sector_analysis_lap_missing_ts", lap_id=lap_id)
                continue

            # Fetch telemetry samples for this lap
            with conn.cursor(f"lap_cursor_{lap_number}") as stream_cur:
                stream_cur.itersize = 2000
                stream_cur.execute(
                    """
                    SELECT time, lat, lon, speed_kph, heading_deg, distance_m
                    FROM telemetry_samples
                    WHERE session_id = %s AND lap_number = %s
                    ORDER BY time
                    """,
                    (session_id, lap_number),
                )
                lap_samples = []
                for row in stream_cur:
                    lap_samples.append({
                        "time": row[0],
                        "lat": float(row[1]) if row[1] is not None else None,
                        "lon": float(row[2]) if row[2] is not None else None,
                        "speed_kph": float(row[3]) if row[3] is not None else None,
                        "heading_deg": float(row[4]) if row[4] is not None else None,
                        "distance_m": float(row[5]) if row[5] is not None else None,
                    })

            if not lap_samples:
                logger.warning("sector_analysis_no_samples", lap_id=lap_id)
                continue

            # Detect crossings
            crossings = detect_sector_crossings(lap_samples, sectors, start_ts, end_ts)

            # Compute sector times
            sector_times = compute_sector_times(crossings, start_ts, end_ts, lap_time_ms or 0)

            # INSERT lap_sectors
            for st in sector_times:
                # Find circuit_sector_id for this sector_number
                sector_meta = next(
                    (s for s in sectors if s["sector_number"] == st["sector_number"]),
                    None,
                )
                if sector_meta is None:
                    continue
                circuit_sector_id = sector_meta["id"]

                cur.execute(
                    """
                    INSERT INTO lap_sectors
                        (lap_id, circuit_sector_id, sector_number, sector_time_ms,
                         entry_speed_kph, exit_speed_kph)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (lap_id, sector_number) DO UPDATE
                        SET sector_time_ms   = EXCLUDED.sector_time_ms,
                            entry_speed_kph  = EXCLUDED.entry_speed_kph,
                            exit_speed_kph   = EXCLUDED.exit_speed_kph
                    """,
                    (
                        lap_id,
                        circuit_sector_id,
                        st["sector_number"],
                        st["sector_time_ms"],
                        st["entry_speed_kph"],
                        st["exit_speed_kph"],
                    ),
                )

            # UPDATE laps.max_speed_kph, min_speed_kph
            speeds = [s["speed_kph"] for s in lap_samples if s.get("speed_kph") is not None]
            if speeds:
                cur.execute(
                    """
                    UPDATE laps
                    SET max_speed_kph = %s, min_speed_kph = %s
                    WHERE id = %s
                    """,
                    (max(speeds), min(speeds), lap_id),
                )

            conn.commit()
            laps_processed += 1
            logger.info("sector_analysis_lap_processed", lap_id=lap_id, sectors=len(sector_times))

        # ------------------------------------------------------------------
        # 5. Update job → done
        # ------------------------------------------------------------------
        result = {"laps_processed": laps_processed, "sectors_per_lap": len(sectors)}
        cur.execute(
            """
            UPDATE analysis_jobs
            SET status = 'done', completed_at = now(), result_summary = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(result), job_id),
        )
        conn.commit()

        logger.info("sector_analysis_task_completed", session_id=session_id, **result)

        # ------------------------------------------------------------------
        # 6. Dispatch ideal_lap_task automatically
        # ------------------------------------------------------------------
        _dispatch_ideal_lap(conn, session_id)

        return result

    except Exception as exc:
        logger.error("sector_analysis_task_failed", error=str(exc), session_id=session_id)
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


def _dispatch_ideal_lap(conn, session_id: str) -> None:
    """Create an ideal_lap job and dispatch the Celery task."""
    try:
        cur = conn.cursor()
        cur.execute("SELECT owner_id FROM sessions WHERE id = %s", (session_id,))
        row = cur.fetchone()
        if row is None:
            return
        owner_id = str(row[0])

        new_job_id = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO analysis_jobs
                (id, session_id, requested_by, job_type, status)
            VALUES (%s, %s, %s, 'ideal_lap', 'queued')
            """,
            (new_job_id, session_id, owner_id),
        )
        conn.commit()

        from worker.app.tasks.ideal_lap import ideal_lap_task
        ideal_lap_task.apply_async(
            args=[session_id, new_job_id],
            queue="analysis",
        )
        logger.info("sector_analysis_dispatched_ideal_lap", job_id=new_job_id)
    except Exception as exc:
        logger.error("sector_analysis_dispatch_failed", error=str(exc))
