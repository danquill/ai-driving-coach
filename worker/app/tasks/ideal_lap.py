"""ideal_lap_task — Celery task for theoretical best lap construction."""

from __future__ import annotations

import json
import os
import pathlib
import sys

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
    name="worker.app.tasks.ideal_lap.ideal_lap_task",
    bind=True,
    queue="analysis",
    max_retries=2,
    default_retry_delay=30,
)
def ideal_lap_task(self, session_id: str, job_id: str) -> dict:
    """
    Construct a theoretical best lap from the fastest sector of each valid lap.
    Sets session.status = 'ready' on completion.
    """
    logger.info("ideal_lap_task_started", session_id=session_id, job_id=job_id)

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
        # 2. Fetch all lap_sectors for this session (join through laps)
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT ls.lap_id, ls.sector_number, ls.sector_time_ms,
                   ls.entry_speed_kph, ls.exit_speed_kph
            FROM lap_sectors ls
            JOIN laps l ON l.id = ls.lap_id
            WHERE l.session_id = %s
            ORDER BY ls.lap_id, ls.sector_number
            """,
            (session_id,),
        )
        sector_rows = cur.fetchall()
        lap_sectors = [
            {
                "lap_id": str(row[0]),
                "sector_number": row[1],
                "sector_time_ms": row[2],
                "entry_speed_kph": float(row[3]) if row[3] is not None else None,
                "exit_speed_kph": float(row[4]) if row[4] is not None else None,
            }
            for row in sector_rows
        ]

        # ------------------------------------------------------------------
        # 3. Fetch all laps for this session
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT id, lap_number, is_outlap, is_inlap, is_valid
            FROM laps
            WHERE session_id = %s
            ORDER BY lap_number
            """,
            (session_id,),
        )
        lap_rows = cur.fetchall()
        laps = [
            {
                "id": str(row[0]),
                "lap_number": row[1],
                "is_outlap": row[2],
                "is_inlap": row[3],
                "is_valid": row[4],
            }
            for row in lap_rows
        ]

        # ------------------------------------------------------------------
        # 4. Construct ideal lap
        # ------------------------------------------------------------------
        from app.services.ideal_lap import construct_ideal_lap  # type: ignore

        ideal = construct_ideal_lap(lap_sectors, laps)
        logger.info(
            "ideal_lap_constructed",
            theoretical_time_ms=ideal["theoretical_time_ms"],
            sectors=len(ideal["sector_sources"]),
        )

        # ------------------------------------------------------------------
        # 5. INSERT into ideal_laps table
        # ------------------------------------------------------------------
        if ideal["theoretical_time_ms"] > 0:
            cur.execute(
                """
                INSERT INTO ideal_laps
                    (session_id, theoretical_time_ms, sector_sources)
                VALUES (%s, %s, %s::jsonb)
                """,
                (
                    session_id,
                    ideal["theoretical_time_ms"],
                    json.dumps(ideal["sector_sources"]),
                ),
            )

        # ------------------------------------------------------------------
        # 6. UPDATE sessions.status = 'ready'
        # ------------------------------------------------------------------
        cur.execute(
            "UPDATE sessions SET status = 'ready' WHERE id = %s",
            (session_id,),
        )

        # ------------------------------------------------------------------
        # 7. Update job → done
        # ------------------------------------------------------------------
        result = {
            "theoretical_time_ms": ideal["theoretical_time_ms"],
            "sector_count": len(ideal["sector_sources"]),
        }
        cur.execute(
            """
            UPDATE analysis_jobs
            SET status = 'done', completed_at = now(), result_summary = %s::jsonb
            WHERE id = %s
            """,
            (json.dumps(result), job_id),
        )
        conn.commit()

        logger.info("ideal_lap_task_completed", session_id=session_id, **result)
        return result

    except Exception as exc:
        logger.error("ideal_lap_task_failed", error=str(exc), session_id=session_id)
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
