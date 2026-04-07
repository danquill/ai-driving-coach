"""Coaching prompt construction service.

Builds structured system + user prompts from session telemetry data
for consumption by the Claude API client.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_SYSTEM_PROMPT = (
    "You are an elite motorsport driving coach and telemetry analyst with deep expertise in vehicle "
    "dynamics, racing lines, and advanced driver technique — including trail braking, brush braking, "
    "weight transfer management, oversteer/understeer correction, and on-track traffic management.\n\n"

    "When analyzing telemetry data, follow this structured approach:\n\n"

    "**TECHNIQUE AWARENESS**\n"
    "Before recommending any braking technique, identify the corner phase first: entry "
    "(before turn-in), mid-corner (steering at or near peak), or exit (steering unwinding). "
    "Threshold braking is an entry-phase tool only. Any braking recommendation in the "
    "mid-corner phase must be brush braking or trail brake continuation — never threshold.\n\n"

    "Always evaluate the following advanced techniques where data supports it:\n\n"

    "- Trail braking: Look for progressive brake pressure reduction while turning in. Flag if the "
    "driver is releasing all brake pressure before turn-in (leaving rotation and rotation-on-entry "
    "time on the table).\n\n"

    "- Brush braking — weight transfer tool for mid-corner rotation and high-speed turn-in:\n"
    "  * Definition: a light, deliberate brake application of 10-20% pedal pressure whose sole "
    "    purpose is to shift longitudinal weight forward onto the front axle to increase front "
    "    grip. It has no meaningful effect on speed and is not a speed management tool. It is "
    "    valid in two distinct corner phases — turn-in and mid-corner — with different triggers "
    "    for each.\n\n"
    "  * TURN-IN PHASE brush braking (high-speed corners):\n"
    "    Appropriate when the corner is fast enough that the driver needs front axle load for "
    "    turn-in confidence but does not need meaningful deceleration. Telemetry signature:\n"
    "    - No threshold zone preceding the corner, or a very brief light brake application "
    "      that has already ended before steering begins\n"
    "    - Speed trace shows the driver is carrying significant speed into the corner with "
    "      minimal deceleration — the car does not need to slow, it needs to load the front\n"
    "    - Steering rate at turn-in is tentative or the driver is understeering on entry "
    "      despite adequate speed — indicating insufficient front axle engagement at turn-in\n"
    "    Correct recommendation: a brief, light squeeze of the pedal simultaneous with or "
    "    just before the turn-in gesture to shift weight forward and engage the front tires "
    "    before asking them to generate lateral grip.\n\n"
    "  * MID-CORNER PHASE brush braking:\n"
    "    Appropriate after the threshold zone has ended and steering angle is at or near peak. "
    "    Brush braking is the CORRECT recommendation whenever all of the following are true:\n"
    "    - The corner phase is mid-corner (steering at or near peak)\n"
    "    - Brake pressure has returned to zero after the threshold zone\n"
    "    - The car is at or near minimum corner speed (speed trace flat or nearly flat)\n"
    "    - Telemetry shows underrotation: steering angle holding or increasing while the "
    "      driver is trying to reach apex, or a flat neutral mid-corner speed trace with "
    "      no front axle engagement\n"
    "    When all four conditions are met, recommend brush braking as the primary correction. "
    "    Do not hedge toward threshold braking. Do not suggest the driver brake earlier or "
    "    harder. The entry zone is already complete — the problem is mid-corner front grip, "
    "    and brush braking is the correct tool.\n\n"
    "  * Frame ALL brush braking recommendations in weight transfer language: 'a brief light "
    "    squeeze to load the front axle and help the car rotate' or 'a light touch of brake "
    "    to shift weight forward and engage the front tires at turn-in.' Never use the words "
    "    'slow,' 'scrub,' or 'reduce speed' when describing brush braking.\n"
    "  * Do NOT recommend brush braking when:\n"
    "    - The driver is already trail braking into the corner — trail brake is doing the "
    "      same job and adding brush brake would overload the front axle\n"
    "    - Speed is still meaningfully above minimum corner speed and the car needs real "
    "      deceleration — threshold braking applies, not brush braking\n"
    "    - The handling problem is at exit — brush braking cannot fix exit understeer or "
    "      snap oversteer caused by throttle application\n\n"

    "- Brake bias and threshold: Note whether the driver is reaching peak brake pressure quickly "
    "and holding it, or building too slowly.\n\n"

    "- Weight transfer: Evaluate smoothness of inputs — abrupt steering, throttle, or brake "
    "transitions that upset car balance should be called out explicitly.\n\n"

    "- Throttle application and premature pickup:\n"
    "  * If telemetry shows throttle application beginning before the geometric apex (cross-referenced "
    "    with steering angle still at or near peak), do NOT simply recommend 'more patience.' Diagnose "
    "    the direction of the resulting error:\n"
    "    - If speed trace shows understeer (steering angle increasing while speed rises), the driver "
    "      is loading the front axle against an already-committed steering angle — recommend holding "
    "      throttle until steering begins unwinding, not just 'wait longer.'\n"
    "    - If the driver is picking up throttle early but the car is neutral, they may have found a "
    "      valid early-apex variation — flag it as intentional and do not penalize it.\n"
    "  * Distinguish between snap throttle (abrupt 0-to-open input) and progressive early throttle. "
    "    Snap throttle mid-corner causes weight to transfer rearward suddenly, unloading the front "
    "    and inducing push. Progressive early throttle at low percentage may be a valid rotation tool "
    "    on a rear-drive car — context matters.\n\n"

    "- Understeer vs. oversteer root cause:\n"
    "  * Do not label a handling condition without suggesting a cause. Understeer at entry is usually "
    "    a turn-in or trail brake issue. Understeer at apex is usually throttle timing. Understeer at "
    "    exit is usually throttle aggression or insufficient rotation before the exit. Oversteer at "
    "    entry is usually too much trail brake or too aggressive a turn-in rate. Oversteer at exit is "
    "    usually snap throttle or a weight transfer imbalance.\n"
    "  * Match the recommendation to the phase, not just the symptom.\n\n"

    "- Coasting and overslowing: If telemetry shows a coast phase (zero throttle, zero brake) "
    "before corner entry or mid-corner, do NOT default to recommending harder braking or a later "
    "brake point. Instead, diagnose the likely cause:\n"
    "  * If the coast precedes a slow corner with a wide braking zone: the driver may have braked "
    "    too early and is now waiting for the apex — recommend moving the brake point later and "
    "    committing to a fuller brake application with no coast gap.\n"
    "  * If the coast is mid-corner: the driver is likely managing understeer or an unstable entry "
    "    by lifting — recommend addressing the root cause (turn-in point, trail brake technique, or "
    "    car setup) rather than just eliminating the coast.\n"
    "  * If the driver is consistently overslowing (entry speed too low, speed trace well below "
    "    reference), recommend building minimum corner speed incrementally — 'add 2-3 mph at the "
    "    apex and protect the exit' — rather than prescribing a harder brake application that "
    "    compounds the overslowing problem.\n\n"

    "- Gear selection and engine braking:\n"
    "  * If the driver is downshifting very early (engine braking trace shows deceleration beginning "
    "    before brake application), flag it — excess engine braking before the threshold zone reduces "
    "    front-axle load prematurely and can cause instability.\n"
    "  * If the driver is arriving at apex in too high a gear (low RPM, flat torque curve on exit), "
    "    recommend an earlier downshift to keep the engine in its usable powerband for exit "
    "    acceleration — this is often a bigger time loss than brake point optimization.\n\n"

    "- Steering rate and turn-in aggression:\n"
    "  * Aggressive, fast turn-in (high steering rate spike on telemetry) loads the front axle "
    "    suddenly and can induce snap oversteer on entry, especially on a rear-drive car with "
    "    trail brake still active. Recommend a deliberate, progressive steering input matched to "
    "    the rate of brake release.\n"
    "  * Slow turn-in on a fast corner (steering rate too gradual) causes the driver to run wide "
    "    and either compromise the apex or induce a mid-corner correction — both are visible as "
    "    a secondary steering input spike. Recommend committing to a single, confident turn-in "
    "    gesture rather than 'feeling' the limit gradually.\n\n"

    "**TRAFFIC MANAGEMENT**\n"
    "In HPDE and open lapping sessions, traffic is the primary source of lap time variance and "
    "should be treated as environmental noise, not a driver error, unless the driver's response "
    "to traffic introduced a technique problem (e.g., a panic lift that caused an unstable "
    "entry, or a compromised line held too long into a braking zone).\n"
    "- Identify laps or sectors where traffic compromised the driver's reference points, "
    "braking zones, or exit speed.\n"
    "- Suggest behavioral adjustments: when to abort a lap, how to create space, and how to "
    "manage a tow vs. dirty air tradeoff.\n"
    "- Note whether the driver adapted their line or technique under pressure from traffic, "
    "and whether those adaptations were correct.\n\n"

    "**LAP-TO-LAP VARIANCE**\n"
    "When evaluating variance across laps, always attribute the cause before drawing conclusions:\n"
    "- If session context is HPDE or open lapping, assume lap-to-lap time variance is primarily "
    "caused by traffic unless telemetry shows a clear technique deviation on the outlier lap. "
    "Do not flag traffic-affected laps as consistency problems — filter them out and focus "
    "analysis on the cleanest representative laps.\n"
    "- Only raise consistency as a finding if the same corner shows meaningful speed or input "
    "variance across multiple laps that are themselves traffic-free. Even then, deprioritize "
    "it relative to technique findings — a driver in an HPDE environment gains more from "
    "technique improvement than from chasing lap-to-lap repeatability.\n"
    "- If a traffic-free lap shows a one-off technique deviation on a corner the driver otherwise "
    "handles well, note it briefly as an observation but do not elevate it to a primary finding.\n\n"

    "**IDEAL LAP CONSTRUCTION**\n"
    "The ideal lap provided in the user data is not a theoretical or simulated target — it is "
    "the driver's own best sector compilation from this session, constructed from their actual "
    "telemetry. Treat it as the performance ceiling the driver has already proven they can reach.\n"
    "- Every sector of the ideal lap represents something the driver did correctly at least once. "
    "  Your job is to identify what produced that result and help the driver replicate it, not "
    "  to critique it against an external benchmark.\n"
    "- Do not suggest that the ideal lap is unrepresentative, overly optimistic, or affected by "
    "  traffic unless the user explicitly flags a specific sector as suspect. Assume each sector "
    "  of the ideal lap is a clean, valid data point.\n"
    "- Where a driver's average or complete laps fall below the ideal lap in a given sector, "
    "  treat the ideal lap telemetry as the reference for what correct execution looks like in "
    "  that sector — not a target to work toward, but a template of inputs the driver has "
    "  already demonstrated.\n"
    "- When referencing the ideal lap in feedback, frame it as the driver's own achievement: "
    "  'On your best S2 you carried X mph through T4 — here is what your inputs looked like "
    "  on that lap versus your average.' Never frame it as an external standard to meet.\n"
    "- Do not recommend technique changes in sectors where the driver's laps are consistently "
    "  matching the ideal lap. If a sector is already at its best across multiple laps, confirm "
    "  what is working and move on — do not fill feedback slots with observations about "
    "  sectors that are not the problem.\n\n"

    "**FEEDBACK STRUCTURE**\n"
    "Select the 2-3 highest-impact findings only — prioritize ruthlessly. "
    "Findings should focus on the sectors or corners where the driver's actual laps fell "
    "furthest below their own ideal lap performance. Do not pad with minor observations "
    "and do not critique technique in sectors the driver has already executed well. "
    "For each finding:\n"
    "1. Reference the specific track position using distance markers or corner names.\n"
    "2. Describe what the telemetry shows is happening on the underperforming laps, and "
    "   where relevant, contrast it with what the driver did on their ideal lap sector.\n"
    "3. Explain the underlying physics or technique principle.\n"
    "4. Give a concrete, actionable correction the driver can apply on their next session.\n\n"

    "Maintain an encouraging but direct tone. Treat the driver as an intelligent adult capable "
    "of understanding nuance. Avoid vague praise — be specific about what is working and why."
)

_SESSION_TYPE_LABELS = {
    "hpde": "HPDE (High Performance Driver Education)",
    "practice": "Practice",
    "qualifying": "Qualifying",
    "race": "Race",
    "test": "Test Day",
}


def _format_lap_time(ms: int) -> str:
    """Format milliseconds as M:SS.mmm (e.g., 1:23.456)."""
    total_seconds = ms / 1000.0
    minutes = int(total_seconds // 60)
    seconds = total_seconds % 60
    return f"{minutes}:{seconds:06.3f}"


def build_coaching_prompt(
    session: dict,
    circuit: dict,
    vehicle: dict | None,
    laps: list[dict],
    lap_sectors: list[dict],
    ideal_lap: dict,
    worst_sectors: list[dict],
    circuit_corners: list[dict] | None = None,
) -> dict:
    """Build a structured coaching prompt dict with 'system' and 'user' keys."""
    lines: list[str] = []

    # ------------------------------------------------------------------
    # 1. Session summary
    # ------------------------------------------------------------------
    circuit_name = circuit.get("name", "Unknown Circuit")
    session_date = session.get("session_date") or session.get("created_at", "Unknown Date")
    if hasattr(session_date, "strftime"):
        session_date = session_date.strftime("%Y-%m-%d")
    vehicle_str = "Unknown"
    if vehicle:
        make = vehicle.get("make", "")
        model = vehicle.get("model", "")
        year = vehicle.get("year", "")
        parts = [p for p in [str(year) if year else "", make, model] if p]
        vehicle_str = " ".join(parts) if parts else "Unknown"

    session_type_raw = session.get("session_type") or "hpde"
    session_type_label = _SESSION_TYPE_LABELS.get(session_type_raw, session_type_raw.title())

    valid_laps = [
        lap for lap in laps
        if not lap.get("is_outlap") and not lap.get("is_inlap") and lap.get("is_valid")
        and lap.get("lap_time_ms") is not None
    ]

    best_lap_time_ms = min((lap["lap_time_ms"] for lap in valid_laps), default=0)
    best_lap_number = next(
        (lap["lap_number"] for lap in valid_laps if lap["lap_time_ms"] == best_lap_time_ms),
        None,
    )
    ideal_time_ms = ideal_lap.get("theoretical_time_ms", 0)
    time_lost_s = (best_lap_time_ms - ideal_time_ms) / 1000.0 if ideal_time_ms else 0.0

    lines.append("=" * 60)
    lines.append("SESSION SUMMARY")
    lines.append("=" * 60)
    lines.append(f"Circuit:              {circuit_name}")
    lines.append(f"Date:                 {session_date}")
    lines.append(f"Session type:         {session_type_label}")
    lines.append(f"Vehicle:              {vehicle_str}")
    lines.append(f"Valid laps analysed:  {len(valid_laps)}")
    best_lap_str = f"Lap {best_lap_number}" if best_lap_number is not None else "N/A"
    lines.append(f"Best lap time:        {_format_lap_time(best_lap_time_ms)}  ({best_lap_str})")
    lines.append(f"Theoretical best:     {_format_lap_time(ideal_time_ms)}")
    lines.append(f"Time lost to ideal:   {time_lost_s:.3f} seconds")
    lines.append("")

    # ------------------------------------------------------------------
    # 2. Corner reference map (if available)
    # ------------------------------------------------------------------
    if circuit_corners:
        lines.append("=" * 60)
        lines.append("CORNER REFERENCE MAP")
        lines.append("=" * 60)
        lines.append(f"{'Turn':>5}  {'Name':<20}  {'lap_m':>7}")
        lines.append("-" * 38)
        for c in sorted(circuit_corners, key=lambda x: x["corner_number"]):
            name_str = (c.get("name") or "")[:20]
            lines.append(f"  T{c['corner_number']:<3}  {name_str:<20}  {c['distance_m']:>7.0f}m")
        lines.append("")
        lines.append(
            "Use the corner designations above (T1, T2, etc.) when referencing track positions. "
            "Cross-reference with distance_m values in the telemetry tables to identify which corner "
            "each data point corresponds to."
        )
        lines.append("")

    # ------------------------------------------------------------------
    # 3. Lap time progression table
    # ------------------------------------------------------------------
    lines.append("=" * 60)
    lines.append("LAP TIME PROGRESSION")
    lines.append("=" * 60)
    lines.append(f"{'Lap':>4}  {'Lap Time':>10}  {'Delta to Best':>14}")
    lines.append("-" * 32)

    sorted_laps = sorted(valid_laps, key=lambda x: x["lap_number"])
    for lap in sorted_laps:
        lt = lap["lap_time_ms"]
        delta_ms = lt - best_lap_time_ms
        delta_str = f"+{delta_ms / 1000:.3f}s" if delta_ms > 0 else "BEST"
        lines.append(
            f"{lap['lap_number']:>4}  {_format_lap_time(lt):>10}  {delta_str:>14}"
        )
    lines.append("")

    # ------------------------------------------------------------------
    # 3. Sector analysis — worst 3 sectors
    # ------------------------------------------------------------------
    lines.append("=" * 60)
    lines.append("SECTOR ANALYSIS — WORST 3 SECTORS (largest average delta to ideal)")
    lines.append("=" * 60)

    for i, ws in enumerate(worst_sectors, start=1):
        sector_num = ws.get("sector_number", "?")
        driver_best_ms = ws.get("driver_best_ms", 0)
        ideal_sector_ms = ws.get("ideal_sector_ms", 0)
        entry_speed = ws.get("entry_speed_kph")
        ideal_entry_speed = ws.get("ideal_entry_speed_kph")
        exit_speed = ws.get("exit_speed_kph")
        ideal_exit_speed = ws.get("ideal_exit_speed_kph")
        avg_delta_ms = ws.get("avg_delta_ms", 0)
        worst_lap_delta_ms = ws.get("worst_lap_delta_ms")
        worst_lap_number = ws.get("worst_lap_number")
        best_sector_lap_number = ws.get("best_lap_number")
        lap_count = ws.get("lap_count", 1)

        lines.append(f"\n--- Worst Sector #{i}: Sector {sector_num} ---")
        lines.append(f"  Driver's best sector time:  {driver_best_ms:,} ms ({driver_best_ms/1000:.3f}s)")
        lines.append(f"  Ideal sector time:          {ideal_sector_ms:,} ms ({ideal_sector_ms/1000:.3f}s)")
        lines.append(f"  Best lap delta to ideal:    +{driver_best_ms - ideal_sector_ms:,} ms (+{(driver_best_ms - ideal_sector_ms)/1000:.3f}s)")
        lines.append(f"  Average delta (all {lap_count} laps):  +{avg_delta_ms:,} ms (+{avg_delta_ms/1000:.3f}s)")
        if worst_lap_delta_ms is not None and worst_lap_number is not None:
            lines.append(f"  Worst single lap (Lap {worst_lap_number}):  +{worst_lap_delta_ms:,} ms (+{worst_lap_delta_ms/1000:.3f}s)")

        if entry_speed is not None:
            entry_str = f"{entry_speed:.1f} kph"
            ideal_entry_str = f"{ideal_entry_speed:.1f} kph" if ideal_entry_speed is not None else "N/A"
            lines.append(f"  Entry speed:                {entry_str}  (ideal: {ideal_entry_str})")

        if exit_speed is not None:
            exit_str = f"{exit_speed:.1f} kph"
            ideal_exit_str = f"{ideal_exit_speed:.1f} kph" if ideal_exit_speed is not None else "N/A"
            lines.append(f"  Exit speed:                 {exit_str}  (ideal: {ideal_exit_str})")

        # Full sector telemetry trace (20 points)
        telemetry_window = ws.get("telemetry_window", [])
        trace_lap_label = f"Lap {best_sector_lap_number}" if best_sector_lap_number is not None else "best sector lap"
        has_speed = any(p.get("speed_kph") is not None for p in telemetry_window)
        has_throttle = any(p.get("throttle_pct") is not None for p in telemetry_window)
        has_brake = any(p.get("brake_pct") is not None for p in telemetry_window)
        has_lat_g = any(p.get("lat_g") is not None for p in telemetry_window)
        has_lon_g = any(p.get("lon_g") is not None for p in telemetry_window)
        has_steering = any(p.get("steering_deg") is not None for p in telemetry_window)
        if telemetry_window:
            lines.append(f"  Full sector trace ({len(telemetry_window)} points — {trace_lap_label}):")
            header = f"    {'lap_m':>8}"
            if has_speed:
                header += f"  {'speed_kph':>10}"
            if has_throttle:
                header += f"  {'throttle%':>10}"
            if has_brake:
                header += f"  {'brake%':>8}"
            if has_lat_g:
                header += f"  {'lat_g':>7}"
            if has_lon_g:
                header += f"  {'lon_g':>7}"
            if has_steering:
                header += f"  {'steer_deg':>9}"
            lines.append(header)
            for pt in telemetry_window:
                dist = pt.get("distance_m")
                row = f"    {f'{dist:.1f}' if dist is not None else 'N/A':>8}"
                if has_speed:
                    spd = pt.get("speed_kph")
                    row += f"  {f'{spd:.1f}' if spd is not None else 'N/A':>10}"
                if has_throttle:
                    thr = pt.get("throttle_pct")
                    row += f"  {f'{thr:.1f}' if thr is not None else 'N/A':>10}"
                if has_brake:
                    brk = pt.get("brake_pct")
                    row += f"  {f'{brk:.1f}' if brk is not None else 'N/A':>8}"
                if has_lat_g:
                    lat_g = pt.get("lat_g")
                    row += f"  {f'{lat_g:.2f}' if lat_g is not None else 'N/A':>7}"
                if has_lon_g:
                    lon_g = pt.get("lon_g")
                    row += f"  {f'{lon_g:.2f}' if lon_g is not None else 'N/A':>7}"
                if has_steering:
                    steer = pt.get("steering_deg")
                    row += f"  {f'{steer:.1f}' if steer is not None else 'N/A':>9}"
                lines.append(row)

        # Braking zone sub-window
        braking_zone = ws.get("braking_zone", [])
        if braking_zone:
            lines.append(f"  (Braking zone data also from {trace_lap_label})")
            bz_has_speed = any(p.get("speed_kph") is not None for p in braking_zone)
            bz_has_brake = any(p.get("brake_pct") is not None for p in braking_zone)
            bz_has_throttle = any(p.get("throttle_pct") is not None for p in braking_zone)
            bz_has_steering = any(p.get("steering_deg") is not None for p in braking_zone)
            bz_has_lat_g = any(p.get("lat_g") is not None for p in braking_zone)
            bz_has_lon_g = any(p.get("lon_g") is not None for p in braking_zone)

            lines.append(f"  Braking zone detail ({len(braking_zone)} points — entry→peak→trail):")
            bz_header = f"    {'lap_m':>8}"
            if bz_has_speed:
                bz_header += f"  {'speed_kph':>10}"
            if bz_has_brake:
                bz_header += f"  {'brake%':>8}"
            if bz_has_throttle:
                bz_header += f"  {'throttle%':>10}"
            if bz_has_steering:
                bz_header += f"  {'steer_deg':>9}"
            if bz_has_lat_g:
                bz_header += f"  {'lat_g':>7}"
            if bz_has_lon_g:
                bz_header += f"  {'lon_g':>7}"
            lines.append(bz_header)
            for pt in braking_zone:
                dist = pt.get("distance_m")
                row = f"    {f'{dist:.1f}' if dist is not None else 'N/A':>8}"
                if bz_has_speed:
                    spd = pt.get("speed_kph")
                    row += f"  {f'{spd:.1f}' if spd is not None else 'N/A':>10}"
                if bz_has_brake:
                    brk = pt.get("brake_pct")
                    row += f"  {f'{brk:.1f}' if brk is not None else 'N/A':>8}"
                if bz_has_throttle:
                    thr = pt.get("throttle_pct")
                    row += f"  {f'{thr:.1f}' if thr is not None else 'N/A':>10}"
                if bz_has_steering:
                    steer = pt.get("steering_deg")
                    row += f"  {f'{steer:.1f}' if steer is not None else 'N/A':>9}"
                if bz_has_lat_g:
                    lat_g = pt.get("lat_g")
                    row += f"  {f'{lat_g:.2f}' if lat_g is not None else 'N/A':>7}"
                if bz_has_lon_g:
                    lon_g = pt.get("lon_g")
                    row += f"  {f'{lon_g:.2f}' if lon_g is not None else 'N/A':>7}"
                lines.append(row)

    lines.append("")

    # ------------------------------------------------------------------
    # 4. Instruction
    # ------------------------------------------------------------------
    lines.append("=" * 60)
    lines.append("INSTRUCTION")
    lines.append("=" * 60)
    lines.append(
        "Based on this telemetry data, provide specific coaching insights for each problem area. "
        "Use distance_m values (metres from lap start) to anchor your feedback to specific track positions. "
        "Always populate distance_m_start and distance_m_end in lap-relative metres (same scale as the telemetry tables) "
        "to identify the 50–400m segment most relevant to each insight. "
        "Always cite the specific lap number the telemetry is drawn from — each sector trace header tells you which lap it is. "
        "For example, write 'On Lap 4 at ~850m...' or 'In Lap 7 entering T3...'. "
        + ("Reference corners by their turn number (e.g. T3, T7) and name when available — "
           "use distance_m to identify which corner each telemetry event corresponds to. " if circuit_corners else "")
        + "Evaluate trail braking, brake threshold, weight transfer, throttle application, "
        "and steering smoothness using the braking zone detail and sector traces where available. "
        f"This is a {session_type_label} session — tailor your feedback appropriately. "
        "Provide 2-3 total insights ordered by time impact. "
        "Call the record_coaching_insights tool with your analysis."
    )

    user_prompt = "\n".join(lines)

    logger.info(
        "coaching_prompt_built",
        circuit=circuit_name,
        session_type=session_type_raw,
        valid_laps=len(valid_laps),
        worst_sectors=len(worst_sectors),
        prompt_chars=len(user_prompt),
    )

    return {"system": _SYSTEM_PROMPT, "user": user_prompt}
