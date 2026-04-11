"""ai_coaching_task — Celery task for generating AI coaching insights via Claude."""

from __future__ import annotations

import json
import math
import os
import pathlib
import re
import sys

import structlog

# ---------------------------------------------------------------------------
# Path setup — make api/app importable
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
# DB helper (sync psycopg2 — mirrors pattern from other tasks)
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
# Haversine distance (metres) between two lat/lon pairs
# ---------------------------------------------------------------------------

def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000.0  # Earth radius in metres
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------

from worker.app.celery_app import app as celery_app  # noqa: E402


@celery_app.task(
    name="worker.app.tasks.ai_coaching.generate_coaching_insights_task",
    bind=True,
    queue="analysis",
    max_retries=2,
    default_retry_delay=60,
)
def generate_coaching_insights_task(self, session_id: str, job_id: str) -> dict:
    """Generate AI coaching insights for a session using Claude."""
    logger.info("ai_coaching_task_started", session_id=session_id, job_id=job_id)

    conn = None
    try:
        conn = _get_sync_db_conn()
        cur = conn.cursor()

        # ------------------------------------------------------------------
        # 1. Update job → running; read input_params
        # ------------------------------------------------------------------
        cur.execute(
            "UPDATE analysis_jobs SET status = 'running', started_at = now() WHERE id = %s RETURNING input_params",
            (job_id,),
        )
        job_row = cur.fetchone()
        conn.commit()

        input_params: dict = {}
        if job_row and job_row[0]:
            raw = job_row[0]
            if isinstance(raw, str):
                input_params = json.loads(raw)
            elif isinstance(raw, dict):
                input_params = raw

        compare_lap_number: int | None = input_params.get("compare_lap_number")

        # ------------------------------------------------------------------
        # 2. Check ANTHROPIC_API_KEY
        # ------------------------------------------------------------------
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            cur.execute(
                """
                UPDATE analysis_jobs
                SET status = 'failed', error_message = %s, completed_at = now()
                WHERE id = %s
                """,
                ("ANTHROPIC_API_KEY not configured", job_id),
            )
            conn.commit()
            logger.error("ai_coaching_no_api_key", session_id=session_id)
            return {"error": "ANTHROPIC_API_KEY not configured"}

        # ------------------------------------------------------------------
        # 3. Fetch session, circuit, vehicle
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT s.id, s.name, s.session_date, s.vehicle_id, s.circuit_id,
                   c.id AS c_id, c.name AS circuit_name,
                   v.id AS v_id, v.make, v.model, v.year,
                   s.session_type
            FROM sessions s
            LEFT JOIN circuits c ON c.id = s.circuit_id
            LEFT JOIN vehicles v ON v.id = s.vehicle_id
            WHERE s.id = %s
            """,
            (session_id,),
        )
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"Session {session_id} not found")

        session = {
            "id": str(row[0]),
            "name": row[1],
            "session_date": row[2],
            "vehicle_id": str(row[3]) if row[3] else None,
            "circuit_id": str(row[4]) if row[4] else None,
            "session_type": row[11] or "hpde",
        }
        circuit = {"id": str(row[5]) if row[5] else None, "name": row[6] or "Unknown Circuit"}
        vehicle = None
        if row[7]:
            vehicle = {"id": str(row[7]), "make": row[8], "model": row[9], "year": row[10]}

        # ------------------------------------------------------------------
        # 4. Fetch valid laps
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT id, lap_number, lap_time_ms, is_outlap, is_inlap, is_valid,
                   start_ts, end_ts
            FROM laps
            WHERE session_id = %s
              AND is_outlap = false
              AND is_inlap = false
              AND is_valid = true
              AND lap_time_ms IS NOT NULL
            ORDER BY lap_number
            """,
            (session_id,),
        )
        lap_rows = cur.fetchall()
        laps = [
            {
                "id": str(r[0]),
                "lap_number": r[1],
                "lap_time_ms": r[2],
                "is_outlap": r[3],
                "is_inlap": r[4],
                "is_valid": r[5],
                "start_ts": r[6],
                "end_ts": r[7],
            }
            for r in lap_rows
        ]

        if not laps:
            raise ValueError("No valid laps found for this session")

        # ------------------------------------------------------------------
        # 4b. If compare_lap_number specified, restrict to compare lap only
        # ------------------------------------------------------------------
        # The ideal lap is the theoretical fastest (best sector compilation).
        # We compare only the user-selected lap against it — no need for the
        # actual best lap in the lap list.
        compare_lap_obj: dict | None = None
        if compare_lap_number is not None:
            compare_lap_obj = next((l for l in laps if l["lap_number"] == compare_lap_number), None)
            if compare_lap_obj is None:
                raise ValueError(f"compare_lap_number {compare_lap_number} not found in valid laps")
            laps = [compare_lap_obj]
            logger.info(
                "ai_coaching_laps_filtered",
                session_id=session_id,
                compare_lap=compare_lap_number,
            )

        # ------------------------------------------------------------------
        # 5. Fetch ideal_lap — fail fast if missing
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT id, theoretical_time_ms, sector_sources
            FROM ideal_laps
            WHERE session_id = %s
            ORDER BY constructed_at DESC
            LIMIT 1
            """,
            (session_id,),
        )
        ideal_row = cur.fetchone()
        if ideal_row is None:
            cur.execute(
                """
                UPDATE analysis_jobs
                SET status = 'failed', error_message = %s, completed_at = now()
                WHERE id = %s
                """,
                ("Run sector analysis first", job_id),
            )
            conn.commit()
            logger.warning("ai_coaching_no_ideal_lap", session_id=session_id)
            return {"error": "Run sector analysis first"}

        sector_sources_raw = ideal_row[2]
        if isinstance(sector_sources_raw, str):
            sector_sources = json.loads(sector_sources_raw)
        else:
            sector_sources = sector_sources_raw or []

        ideal_lap = {
            "id": str(ideal_row[0]),
            "theoretical_time_ms": ideal_row[1],
            "sector_sources": sector_sources,
        }

        # ------------------------------------------------------------------
        # 6. Fetch all lap_sectors for this session
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT ls.lap_id, ls.sector_number, ls.sector_time_ms,
                   ls.entry_speed_kph, ls.exit_speed_kph, l.lap_number
            FROM lap_sectors ls
            JOIN laps l ON l.id = ls.lap_id
            WHERE l.session_id = %s
            ORDER BY ls.lap_id, ls.sector_number
            """,
            (session_id,),
        )
        ls_rows = cur.fetchall()
        lap_sectors = [
            {
                "lap_id": str(r[0]),
                "sector_number": r[1],
                "sector_time_ms": r[2],
                "entry_speed_kph": float(r[3]) if r[3] is not None else None,
                "exit_speed_kph": float(r[4]) if r[4] is not None else None,
                "lap_number": r[5],
            }
            for r in ls_rows
        ]

        # ------------------------------------------------------------------
        # 7. Identify worst 3 sectors
        # ------------------------------------------------------------------
        # Build maps from ideal lap sector_sources:
        #   sector_number → ideal sector time / entry speed / exit speed / lap_id
        ideal_sector_time_map: dict[int, int] = {}
        ideal_entry_speed_map: dict[int, float | None] = {}
        ideal_exit_speed_map: dict[int, float | None] = {}
        # Map sector_number → lap_number of the lap that sourced the ideal sector
        ideal_source_lap_map: dict[int, int | None] = {}
        for src in sector_sources:
            sn = src.get("sector_number")
            if sn is None:
                continue
            ideal_sector_time_map[sn] = src.get("sector_time_ms", 0)
            # Resolve lap_id → lap_number so prompt can identify the source lap
            src_lap_id = src.get("lap_id")
            src_lap_num = None
            if src_lap_id:
                src_lap = next((l for l in laps if str(l["id"]) == str(src_lap_id)), None)
                src_lap_num = src_lap["lap_number"] if src_lap else None
            ideal_source_lap_map[sn] = src_lap_num

        # Fetch ideal entry/exit speeds from lap_sectors for the ideal source laps
        for src in sector_sources:
            sn = src.get("sector_number")
            ideal_lap_id = src.get("lap_id")
            if sn is None or ideal_lap_id is None:
                continue
            for ls in lap_sectors:
                if str(ls["lap_id"]) == str(ideal_lap_id) and ls["sector_number"] == sn:
                    ideal_entry_speed_map[sn] = ls.get("entry_speed_kph")
                    ideal_exit_speed_map[sn] = ls.get("exit_speed_kph")
                    break

        # Compare every lap's sector time against the ideal sector time.
        # The ideal lap is constructed FROM the driver's best sectors, so comparing
        # the driver's single best sector to ideal always yields 0. Instead we
        # find the per-sector average delta across all laps, then pick the sectors
        # where the driver most consistently loses time — these are the most
        # coachable opportunities.
        lap_id_set = {lap["id"] for lap in laps}

        # Accumulate all sector times per sector number
        sector_times_by_num: dict[int, list[dict]] = {}
        for ls in lap_sectors:
            if ls["lap_id"] not in lap_id_set:
                continue
            sn = ls["sector_number"]
            if sn not in sector_times_by_num:
                sector_times_by_num[sn] = []
            sector_times_by_num[sn].append(ls)

        sector_deltas = []
        for sn, entries in sector_times_by_num.items():
            ideal_time = ideal_sector_time_map.get(sn)
            if ideal_time is None or ideal_time == 0:
                continue

            # With a single compare lap, delta is just that lap vs ideal
            compare_entry = entries[0]
            delta_ms = compare_entry["sector_time_ms"] - ideal_time
            compare_lap_info = next((l for l in laps if l["id"] == compare_entry["lap_id"]), None)

            sector_deltas.append({
                "sector_number": sn,
                "driver_best_ms": compare_entry["sector_time_ms"],
                "ideal_sector_ms": ideal_time,
                "avg_delta_ms": round(delta_ms),
                "delta_ms": round(delta_ms),
                "compare_lap_number": compare_lap_info["lap_number"] if compare_lap_info else compare_lap_number,
                "lap_count": 1,
                "entry_speed_kph": compare_entry.get("entry_speed_kph"),
                "exit_speed_kph": compare_entry.get("exit_speed_kph"),
                "ideal_entry_speed_kph": ideal_entry_speed_map.get(sn),
                "ideal_exit_speed_kph": ideal_exit_speed_map.get(sn),
                "best_lap_id": compare_entry["lap_id"],
                "ideal_source_lap_number": ideal_source_lap_map.get(sn),
            })

        # Sort by average delta descending — most time lost first
        sector_deltas.sort(key=lambda x: x["avg_delta_ms"], reverse=True)
        worst_3 = sector_deltas[:3]

        # ------------------------------------------------------------------
        # 8. Fetch circuit_sectors for distance boundaries + corners for prompt
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT cs.sector_number, cs.trigger_lat, cs.trigger_lon
            FROM circuit_sectors cs
            JOIN sessions s ON s.circuit_id = cs.circuit_id
            WHERE s.id = %s
            ORDER BY cs.sector_number
            """,
            (session_id,),
        )
        cs_rows = cur.fetchall()
        circuit_sectors = [
            {
                "sector_number": r[0],
                "trigger_lat": float(r[1]),
                "trigger_lon": float(r[2]),
            }
            for r in cs_rows
        ]

        cur.execute(
            """
            SELECT cc.corner_number, cc.name, cc.distance_m
            FROM circuit_corners cc
            JOIN sessions s ON s.circuit_id = cc.circuit_id
            WHERE s.id = %s
            ORDER BY cc.corner_number
            """,
            (session_id,),
        )
        corner_rows = cur.fetchall()
        circuit_corners = [
            {
                "corner_number": r[0],
                "name": r[1],
                "distance_m": float(r[2]),
            }
            for r in corner_rows
        ]

        # ------------------------------------------------------------------
        # 9. Compute session-wide normalization ranges for throttle/brake
        #    Devices often have calibration offsets (e.g. throttle 9–91 instead
        #    of 0–100). Normalize to 0–100 so the coach isn't confused by
        #    apparent simultaneous throttle/brake or partial inputs at rest.
        # ------------------------------------------------------------------
        cur.execute(
            """
            SELECT
                percentile_cont(0.02) WITHIN GROUP (ORDER BY throttle_pct) AS thr_min,
                max(throttle_pct) AS thr_max,
                percentile_cont(0.02) WITHIN GROUP (ORDER BY brake_pct)    AS brk_min,
                max(brake_pct)    AS brk_max
            FROM telemetry_samples
            WHERE session_id = %s
              AND lap_number IN %s
            """,
            (session_id, tuple(l["lap_number"] for l in laps)),
        )
        norm_row = cur.fetchone()
        thr_min = float(norm_row[0]) if norm_row[0] is not None else 0.0
        thr_max = float(norm_row[1]) if norm_row[1] is not None else 100.0
        brk_min = float(norm_row[2]) if norm_row[2] is not None else 0.0
        brk_max = float(norm_row[3]) if norm_row[3] is not None else 100.0

        def _norm(value: float | None, lo: float, hi: float) -> float | None:
            if value is None:
                return None
            if hi <= lo:
                return value
            return round(max(0.0, min(100.0, (value - lo) / (hi - lo) * 100.0)), 1)

        # ------------------------------------------------------------------
        # 10. Build telemetry window for each worst sector
        # ------------------------------------------------------------------
        for ws in worst_3:
            sn = ws["sector_number"]
            lap_id = ws["best_lap_id"]
            lap_info = next((l for l in laps if l["id"] == lap_id), None)
            lap_number = None
            if lap_info:
                lap_number = lap_info["lap_number"]
            ws["best_lap_number"] = lap_number

            # Identify sector start/end triggers
            # Sector N starts at the previous sector's trigger, sector 1 starts at 0
            sorted_cs = sorted(circuit_sectors, key=lambda x: x["sector_number"])
            sector_trigger = next((c for c in sorted_cs if c["sector_number"] == sn), None)
            prev_trigger = None
            for c in sorted_cs:
                if c["sector_number"] < sn:
                    prev_trigger = c

            telemetry_window = []
            if lap_number is not None and sector_trigger is not None:
                # Fetch all telemetry samples for this lap
                cur.execute(
                    """
                    SELECT time, lat, lon, speed_kph, throttle_pct, brake_pct,
                           lat_g, lon_g, distance_m, steering_deg
                    FROM telemetry_samples
                    WHERE session_id = %s AND lap_number = %s
                    ORDER BY time
                    """,
                    (session_id, lap_number),
                )
                telem_rows = cur.fetchall()
                all_samples = [
                    {
                        "time": r[0],
                        "lat": float(r[1]) if r[1] is not None else None,
                        "lon": float(r[2]) if r[2] is not None else None,
                        "speed_kph": float(r[3]) if r[3] is not None else None,
                        "throttle_pct": float(r[4]) if r[4] is not None else None,
                        "brake_pct": float(r[5]) if r[5] is not None else None,
                        "lat_g": float(r[6]) if r[6] is not None else None,
                        "lon_g": float(r[7]) if r[7] is not None else None,
                        "distance_m": float(r[8]) if r[8] is not None else None,
                        "steering_deg": float(r[9]) if r[9] is not None else None,
                    }
                    for r in telem_rows
                ]

                if all_samples:
                    # Compute lap start distance for normalising distance_m to lap-relative
                    lap_start_dist = min(
                        (s["distance_m"] for s in all_samples if s["distance_m"] is not None),
                        default=0.0,
                    )

                    # Find start sample: nearest to prev sector trigger (or first sample)
                    if prev_trigger:
                        start_idx = min(
                            range(len(all_samples)),
                            key=lambda i: _haversine_m(
                                all_samples[i]["lat"] or 0,
                                all_samples[i]["lon"] or 0,
                                prev_trigger["trigger_lat"],
                                prev_trigger["trigger_lon"],
                            ) if all_samples[i]["lat"] is not None else float("inf"),
                        )
                    else:
                        start_idx = 0

                    # Find end sample: nearest to this sector's trigger
                    end_idx = min(
                        range(len(all_samples)),
                        key=lambda i: _haversine_m(
                            all_samples[i]["lat"] or 0,
                            all_samples[i]["lon"] or 0,
                            sector_trigger["trigger_lat"],
                            sector_trigger["trigger_lon"],
                        ) if all_samples[i]["lat"] is not None else float("inf"),
                    )

                    # Make sure start < end
                    if start_idx >= end_idx and end_idx < len(all_samples) - 1:
                        start_idx = max(0, end_idx - 1)

                    sector_samples = all_samples[start_idx : end_idx + 1]

                    # Pick 20 evenly-spaced points through sector
                    n_points = 20
                    if len(sector_samples) >= n_points:
                        indices = [
                            int(round(i * (len(sector_samples) - 1) / (n_points - 1)))
                            for i in range(n_points)
                        ]
                        chosen = [sector_samples[idx] for idx in indices]
                    else:
                        chosen = sector_samples

                    def _lap_dist(s: dict) -> float | None:
                        d = s.get("distance_m")
                        return round(d - lap_start_dist, 1) if d is not None else None

                    telemetry_window = [
                        {
                            "distance_m": _lap_dist(s),
                            "speed_kph": s.get("speed_kph"),
                            "throttle_pct": _norm(s.get("throttle_pct"), thr_min, thr_max),
                            "brake_pct": _norm(s.get("brake_pct"), brk_min, brk_max),
                            "lat_g": s.get("lat_g"),
                            "lon_g": s.get("lon_g"),
                            "steering_deg": s.get("steering_deg"),
                        }
                        for s in chosen
                    ]

                    # ----------------------------------------------------------
                    # Braking zone sub-window: find peak brake sample and extract
                    # ~10 samples around it (entry → peak → trail-off) to show
                    # brake shape for trail braking analysis
                    # ----------------------------------------------------------
                    braking_zone = []
                    brake_values = [
                        _norm(s.get("brake_pct"), brk_min, brk_max) or 0.0
                        for s in sector_samples
                    ]
                    if max(brake_values) > 15.0:  # only if meaningful braking exists (above noise floor)
                        peak_idx = brake_values.index(max(brake_values))
                        # Window: up to 15 samples before peak (entry) and 10 after (trail)
                        bz_start = max(0, peak_idx - 15)
                        bz_end = min(len(sector_samples) - 1, peak_idx + 10)
                        bz_samples = sector_samples[bz_start : bz_end + 1]
                        # Downsample to at most 12 points
                        n_bz = min(12, len(bz_samples))
                        if len(bz_samples) > n_bz:
                            bz_indices = [
                                int(round(i * (len(bz_samples) - 1) / (n_bz - 1)))
                                for i in range(n_bz)
                            ]
                            bz_samples = [bz_samples[i] for i in bz_indices]
                        braking_zone = [
                            {
                                "distance_m": _lap_dist(s),
                                "speed_kph": s.get("speed_kph"),
                                "brake_pct": _norm(s.get("brake_pct"), brk_min, brk_max),
                                "throttle_pct": _norm(s.get("throttle_pct"), thr_min, thr_max),
                                "steering_deg": s.get("steering_deg"),
                                "lat_g": s.get("lat_g"),
                                "lon_g": s.get("lon_g"),
                            }
                            for s in bz_samples
                        ]

                    ws["braking_zone"] = braking_zone

            ws["telemetry_window"] = telemetry_window

        # ------------------------------------------------------------------
        # 10. Build the prompt and pre-compute corner classifications
        # ------------------------------------------------------------------
        from app.services.coaching_prompt import (  # type: ignore
            build_coaching_prompt,
            classify_corners,
            format_corner_classifications,
            format_corner_knowledge,
        )
        from app.services.claude_client import ClaudeClient  # type: ignore

        prompt_data = build_coaching_prompt(
            session=session,
            circuit=circuit,
            vehicle=vehicle,
            laps=laps,
            lap_sectors=lap_sectors,
            ideal_lap=ideal_lap,
            worst_sectors=worst_3,
            circuit_corners=circuit_corners,
        )

        # ------------------------------------------------------------------
        # 10b. Fetch circuit corner knowledge
        # ------------------------------------------------------------------
        corner_knowledge: list[dict] = []
        if circuit.get("id"):
            cur.execute(
                """
                SELECT id, corner_number, typical_phase_of_interest,
                       known_handling_tendency, correct_technique,
                       incorrect_recommendations, coaching_notes, source
                FROM circuit_corner_knowledge
                WHERE circuit_id = %s
                ORDER BY COALESCE(corner_number, 0), created_at
                """,
                (circuit["id"],),
            )
            corner_knowledge = [
                {
                    "id": str(r[0]),
                    "corner_number": r[1],
                    "typical_phase_of_interest": r[2],
                    "known_handling_tendency": r[3],
                    "correct_technique": r[4],
                    "incorrect_recommendations": r[5] or [],
                    "coaching_notes": r[6],
                    "source": r[7],
                }
                for r in cur.fetchall()
            ]
            logger.info(
                "ai_coaching_knowledge_fetched",
                session_id=session_id,
                knowledge_count=len(corner_knowledge),
            )

        classifications = classify_corners(
            worst_sectors=worst_3,
            circuit_corners=circuit_corners,
            ideal_lap=ideal_lap,
            lap_sectors=lap_sectors,
        )
        corner_classifications_text = format_corner_classifications(classifications)
        knowledge_block = format_corner_knowledge(corner_knowledge, circuit_corners)

        # Prepend knowledge constraints to Call 1 user message
        if knowledge_block:
            corner_classifications_text = knowledge_block + "\n\n" + corner_classifications_text

        logger.info(
            "ai_coaching_classifications_built",
            session_id=session_id,
            corner_count=len(classifications),
            has_knowledge=bool(knowledge_block),
            windows=[
                {
                    "corner": c["corner_name"],
                    "start": c.get("window_start_m"),
                    "end": c.get("window_end_m"),
                    "compare_lap": c.get("compare_lap_number"),
                }
                for c in classifications
            ],
        )

        # ------------------------------------------------------------------
        # 11. Call Claude (two-call pipeline)
        # ------------------------------------------------------------------
        claude = ClaudeClient(api_key=api_key)
        insights, prompt_tokens, completion_tokens = claude.generate_coaching_insights(
            prompt_data,
            corner_classifications_text=corner_classifications_text,
            knowledge_constraint_text=knowledge_block or None,
        )

        logger.info(
            "ai_coaching_claude_done",
            session_id=session_id,
            insights=len(insights),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        # ------------------------------------------------------------------
        # 12. Insert insights into coaching_insights table
        # ------------------------------------------------------------------
        # Build a distance lookup keyed by corner_name (exact, lowercase).
        # Claude returns corner_name verbatim from the data so this is reliable.
        corner_distance_lookup: dict[str, tuple[float | None, float | None]] = {
            cls["corner_name"].lower(): (cls.get("window_start_m"), cls.get("window_end_m"))
            for cls in classifications
        }

        def _resolve_distances(insight_dict: dict) -> tuple[float | None, float | None]:
            """Resolve distances from corner_name field Claude returns."""
            cn = (insight_dict.get("corner_name") or "").lower().strip()
            if cn and cn in corner_distance_lookup:
                return corner_distance_lookup[cn]
            # Fallback: scan insight text for any known corner name (longest first)
            text_lower = insight_dict.get("insight_text", "").lower()
            for key in sorted(corner_distance_lookup.keys(), key=len, reverse=True):
                if re.search(r'\b' + re.escape(key) + r'\b', text_lower):
                    return corner_distance_lookup[key]
            # Last resort: worst (first) classification's window
            if classifications:
                first = classifications[0]
                return first.get("window_start_m"), first.get("window_end_m")
            return None, None

        insight_count = 0
        for insight in insights:
            # Guard against Claude returning strings instead of objects
            if not isinstance(insight, dict):
                logger.warning("ai_coaching_insight_not_dict", insight=str(insight)[:200])
                continue
            category = insight.get("category", "general")
            insight_text = insight.get("insight_text", "")
            # Strip any disclaimer Claude adds about distances
            insight_text = re.sub(
                r"\s*[\(\[]?[Aa]nalysis window[^)\]]*[\)\]]?\.?",
                "",
                insight_text,
            ).strip()
            insight_text = re.sub(
                r"\s*[\(\[]?[Dd]istance[^)\]]*(?:not provided|UNKNOWN|unavailable)[^)\]]*[\)\]]?\.?",
                "",
                insight_text,
            ).strip()
            confidence = insight.get("confidence", 0.5)
            distance_m_start, distance_m_end = _resolve_distances(insight)
            logger.info(
                "ai_coaching_insight_distances",
                corner_name=insight.get("corner_name"),
                resolved_start=distance_m_start,
                resolved_end=distance_m_end,
                lookup_keys=list(corner_distance_lookup.keys()),
            )

            # Resolve lap_number from classification data (always the compare lap).
            cn = (insight.get("corner_name") or "").lower().strip()
            cls_match = next((c for c in classifications if c["corner_name"].lower() == cn), None)
            insight_lap_number = (
                cls_match.get("compare_lap_number") if cls_match else compare_lap_number
            )
            insight_lap_id = None
            if insight_lap_number is not None:
                lap_match = next((l for l in laps if l["lap_number"] == insight_lap_number), None)
                if lap_match:
                    insight_lap_id = lap_match["id"]

            cur.execute(
                """
                INSERT INTO coaching_insights
                    (session_id, lap_id, lap_number, analysis_job_id, category, insight_text,
                     confidence, distance_m_start, distance_m_end,
                     model_version, prompt_tokens, completion_tokens)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    session_id,
                    insight_lap_id,
                    insight_lap_number,
                    job_id,
                    category,
                    insight_text,
                    confidence,
                    distance_m_start,
                    distance_m_end,
                    "claude-sonnet-4-6",
                    prompt_tokens,
                    completion_tokens,
                ),
            )
            insight_count += 1

        conn.commit()

        # ------------------------------------------------------------------
        # 13. Update job → done
        # ------------------------------------------------------------------
        result = {
            "insight_count": insight_count,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
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

        logger.info("ai_coaching_task_completed", session_id=session_id, **result)
        return result

    except Exception as exc:
        logger.error("ai_coaching_task_failed", error=str(exc), session_id=session_id)
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
