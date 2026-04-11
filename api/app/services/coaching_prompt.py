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


def _kph_to_mph(kph: float | None) -> float | None:
    if kph is None:
        return None
    return round(kph * 0.621371, 1)


def _detect_corner_phase(
    points: list[dict],
    steering_peak: float,
) -> str:
    """Classify the most representative phase for a telemetry window.

    steering_peak should be the known maximum steering angle for the full corner
    (not just the window). When the window is the full sector trace, this equals
    max(abs(steering_deg)) over the window.

    Detection order (strongest signals first):
    1. Entry:      majority of points have brake_pct > 5 (brake is the dominant signal)
    2. Exit:       meaningful throttle present (avg throttle > 5%) — throttle is the
                   clearest exit signal regardless of steering trend
    3. Turn-in:    steering loading (last-third avg > first-third avg × 1.2), brake < 15%
    4. Mid-corner: fallthrough

    Returns the dominant phase label for the window.
    """
    if not points or steering_peak is None or steering_peak == 0:
        return "entry"

    steers = [abs(p.get("steering_deg") or 0) for p in points]
    brakes = [(p.get("brake_pct") or 0) for p in points]
    throttles = [(p.get("throttle_pct") or 0) for p in points]

    majority = len(points) // 2

    # --- 1. Entry: brake is the dominant input ---
    brake_active_count = sum(1 for b in brakes if b > 15)
    if brake_active_count > majority:
        return "entry"

    # --- 2. Exit: meaningful throttle present ---
    avg_throttle = sum(throttles) / len(throttles)
    if avg_throttle > 15:
        return "exit"

    # --- 3. Turn-in: steering clearly loading, brake absent ---
    if len(steers) >= 3:
        n3 = max(1, len(steers) // 3)
        first_third_avg = sum(steers[:n3]) / n3
        last_third_avg = sum(steers[-n3:]) / n3
        max_brake = max(brakes)
        if last_third_avg > first_third_avg * 1.2 and max_brake < 15:
            return "turn-in"

    # --- 4. Mid-corner fallthrough ---
    return "mid-corner"


def classify_corners(
    worst_sectors: list[dict],
    circuit_corners: list[dict] | None,
    ideal_lap: dict,
    lap_sectors: list[dict],
) -> list[dict]:
    """Pre-compute a structured corner classification block for each worst sector.

    For each sector in worst_sectors, produces a classification dict describing:
    - Corner identity (name, distance)
    - Phase of interest (entry / turn-in / mid-corner / exit)
    - Speed comparison vs ideal lap at that phase
    - Brake trace characteristics
    - Steering state
    - Throttle state
    - Engine braking presence
    - Classification summary (front axle state, deceleration need, handling condition)

    Args:
        worst_sectors: list of sector dicts (with telemetry_window and braking_zone)
        circuit_corners: list of corner dicts with corner_number, name, distance_m
        ideal_lap: ideal_lap dict with sector_sources
        lap_sectors: all lap_sectors rows for the session

    Returns:
        list of classification dicts, one per sector in worst_sectors.
    """
    corner_map: dict[float, dict] = {}
    if circuit_corners:
        for c in circuit_corners:
            corner_map[float(c["distance_m"])] = c

    # Build ideal sector time map for speed comparisons
    ideal_sources: list[dict] = ideal_lap.get("sector_sources") or []
    ideal_sector_map: dict[int, dict] = {}
    for src in ideal_sources:
        sn = src.get("sector_number")
        if sn is not None:
            ideal_sector_map[sn] = src

    classifications: list[dict] = []

    for ws in worst_sectors:
        sector_num = ws.get("sector_number", "?")
        telemetry = ws.get("telemetry_window") or []
        braking_zone = ws.get("braking_zone") or []

        # --- Corner identity ---
        # Find the nearest named corner by distance_m to the sector midpoint
        corner_name = f"Sector {sector_num}"
        corner_distance_m: float | None = None
        if telemetry and circuit_corners:
            mid_dist = telemetry[len(telemetry) // 2].get("distance_m") or 0.0
            nearest = min(circuit_corners, key=lambda c: abs(c["distance_m"] - mid_dist))
            corner_name = nearest.get("name") or f"T{nearest['corner_number']}"
            corner_distance_m = nearest["distance_m"]
        elif telemetry:
            corner_distance_m = telemetry[0].get("distance_m")

        # --- Steering peak for phase detection ---
        all_steers = [abs(p.get("steering_deg") or 0) for p in telemetry]
        steering_peak = max(all_steers) if all_steers else 0.0

        # --- Phase detection ---
        phase = _detect_corner_phase(telemetry, steering_peak)

        # --- Speed at phase (driver vs ideal) ---
        # Prefer the pre-computed entry/exit speed fields from the sector record,
        # falling back to reading directly from the telemetry window.
        driver_speed_kph: float | None = None
        ideal_speed_kph: float | None = None

        if phase in ("entry", "turn-in"):
            driver_speed_kph = ws.get("entry_speed_kph") or (telemetry[0].get("speed_kph") if telemetry else None)
            ideal_speed_kph = ws.get("ideal_entry_speed_kph")
        elif phase in ("mid-corner", "exit"):
            driver_speed_kph = ws.get("exit_speed_kph") or (telemetry[len(telemetry) // 2].get("speed_kph") if telemetry else None)
            ideal_speed_kph = ws.get("ideal_exit_speed_kph")

        driver_speed_mph = _kph_to_mph(driver_speed_kph)
        ideal_speed_mph = _kph_to_mph(ideal_speed_kph)
        speed_delta_mph: float | None = None
        if driver_speed_mph is not None and ideal_speed_mph is not None:
            speed_delta_mph = round(driver_speed_mph - ideal_speed_mph, 1)

        # --- Brake trace ---
        brake_description = "zero"
        peak_brake = 0.0
        brake_build_s: float | None = None

        if braking_zone:
            brakes = [p.get("brake_pct") or 0.0 for p in braking_zone]
            peak_brake = max(brakes)
            peak_idx_bz = brakes.index(peak_brake)
            # Estimate build time: samples before peak where brake was < 20% of peak
            threshold_20 = peak_brake * 0.20
            onset_idx = next(
                (i for i in range(peak_idx_bz) if brakes[i] >= threshold_20),
                peak_idx_bz,
            )
            # Rough time estimate: assume ~10 Hz sample rate
            brake_build_s = round((peak_idx_bz - onset_idx) * 0.1, 2)

            # Classify brake trace shape
            if peak_brake >= 60:
                brake_description = f"threshold (peak {peak_brake:.0f}%, built in {brake_build_s}s)"
            elif peak_brake >= 15:
                # Check if it's trail-like (progressive reduction after peak)
                post_peak = brakes[peak_idx_bz:]
                if len(post_peak) >= 3 and post_peak[-1] < peak_brake * 0.5:
                    brake_description = f"trail (peak {peak_brake:.0f}%, progressive release)"
                else:
                    brake_description = f"light ({peak_brake:.0f}%)"
            # below 15% is noise floor — treat as zero
        elif telemetry:
            brakes_tel = [p.get("brake_pct") or 0.0 for p in telemetry]
            peak_brake = max(brakes_tel)
            if peak_brake >= 15:
                brake_description = f"light ({peak_brake:.0f}%)"

        # --- Steering state ---
        steer_state = "neutral"
        if telemetry and steering_peak > 0:
            pct_lock = round(steering_peak, 1)
            steers = [abs(p.get("steering_deg") or 0) for p in telemetry]
            mid = len(steers) // 2
            if mid > 0:
                first_avg = sum(steers[:mid]) / mid
                last_avg = sum(steers[mid:]) / max(1, len(steers[mid:]))
                if last_avg > first_avg * 1.15:
                    trend = "loading"
                elif last_avg < first_avg * 0.85:
                    trend = "unwinding"
                else:
                    trend = "holding"
            else:
                trend = "holding"
            steer_state = f"{pct_lock:.0f}° lock, {trend}"

        # --- Throttle state ---
        throttle_state = "zero"
        if telemetry:
            throttles = [p.get("throttle_pct") or 0.0 for p in telemetry]
            peak_throttle = max(throttles)
            avg_throttle = sum(throttles) / len(throttles)
            if avg_throttle >= 15:
                throttle_state = f"avg {avg_throttle:.0f}% (peak {peak_throttle:.0f}%)"
            elif peak_throttle >= 80:
                # High peak but low avg = driver was full throttle then lifted into the corner
                throttle_state = f"full throttle then lifted (peak {peak_throttle:.0f}%, avg {avg_throttle:.0f}%)"
            elif peak_throttle >= 15:
                throttle_state = f"partial — avg {avg_throttle:.0f}%, peak {peak_throttle:.0f}%"

        # --- Engine braking: lon_g negative while brake=0 ---
        engine_braking = "none"
        if telemetry:
            for p in telemetry:
                lon_g = p.get("lon_g")
                brk = p.get("brake_pct") or 0.0
                if lon_g is not None and lon_g < -0.05 and brk < 15:
                    engine_braking = "active"
                    break

        # --- Classification summary ---
        # Front axle state
        if peak_brake >= 15 or (phase == "turn-in" and peak_brake >= 15):
            front_axle_state = "loaded"
        elif phase == "mid-corner" and peak_brake < 15:
            front_axle_state = "unloaded"
        else:
            front_axle_state = "transitioning"

        # Deceleration need
        if phase == "entry" and peak_brake >= 15:
            decel_need = "yes"
        elif phase in ("mid-corner", "exit"):
            decel_need = "already complete"
        else:
            decel_need = "no"

        # Handling condition from steering trend + speed
        handling_condition = "neutral"
        if telemetry:
            steers = [abs(p.get("steering_deg") or 0) for p in telemetry]
            speeds = [p.get("speed_kph") or 0.0 for p in telemetry]
            throttles = [p.get("throttle_pct") or 0.0 for p in telemetry]
            # Coast: brake and throttle both zero, speed above minimum
            zero_throttle = all(t < 15 for t in throttles)
            zero_brake = all((p.get("brake_pct") or 0) < 15 for p in telemetry)
            if zero_throttle and zero_brake and min(speeds) > 30:
                handling_condition = "coasting"
            # Understeer: steering holding/increasing while speed dropping and throttle on
            elif phase in ("mid-corner", "exit"):
                mid = len(steers) // 2
                if mid > 0:
                    steer_late = sum(steers[mid:]) / max(1, len(steers[mid:]))
                    steer_early = sum(steers[:mid]) / mid
                    throttle_late = sum(throttles[mid:]) / max(1, len(throttles[mid:]))
                    if steer_late >= steer_early * 0.95 and throttle_late > 10:
                        handling_condition = "understeering"

        # Overslowing: entry speed well below ideal
        if (
            speed_delta_mph is not None
            and speed_delta_mph < -5
            and phase in ("entry", "turn-in")
        ):
            handling_condition = "overslowing"

        # Distance range from the telemetry window (lap-relative metres)
        distances = [p["distance_m"] for p in telemetry if p.get("distance_m") is not None]
        window_start_m = round(min(distances), 0) if distances else None
        window_end_m = round(max(distances), 0) if distances else None

        # Focus window anchored on the corner marker distance.
        # Phase-appropriate offsets:
        #   entry/turn-in: 100m before the corner to 50m after (braking zone leads the corner)
        #   mid-corner:    30m before to 80m after (apex region)
        #   exit:          0m before to 120m after (throttle application zone)
        focus_start_m: float | None = None
        focus_end_m: float | None = None
        if corner_distance_m is not None:
            if phase in ("entry", "turn-in"):
                focus_start_m = round(max(0, corner_distance_m - 100), 0)
                focus_end_m = round(corner_distance_m + 50, 0)
            elif phase == "mid-corner":
                focus_start_m = round(max(0, corner_distance_m - 30), 0)
                focus_end_m = round(corner_distance_m + 80, 0)
            else:  # exit
                focus_start_m = round(max(0, corner_distance_m - 10), 0)
                focus_end_m = round(corner_distance_m + 120, 0)
        else:
            # No corner marker — fall back to full sector window
            focus_start_m = window_start_m
            focus_end_m = window_end_m

        classifications.append({
            "corner_name": corner_name,
            "corner_distance_m": corner_distance_m,
            "sector_number": sector_num,
            "phase": phase,
            "driver_speed_mph": driver_speed_mph,
            "ideal_speed_mph": ideal_speed_mph,
            "speed_delta_mph": speed_delta_mph,
            "brake_description": brake_description,
            "steer_state": steer_state,
            "throttle_state": throttle_state,
            "engine_braking": engine_braking,
            "front_axle_state": front_axle_state,
            "decel_need": decel_need,
            "handling_condition": handling_condition,
            "avg_delta_ms": ws.get("avg_delta_ms", 0),
            "ideal_sector_ms": ws.get("ideal_sector_ms", 0),
            "driver_best_ms": ws.get("driver_best_ms", 0),
            "ideal_source_lap_number": ws.get("ideal_source_lap_number"),
            "compare_lap_number": ws.get("compare_lap_number"),
            "window_start_m": focus_start_m,
            "window_end_m": focus_end_m,
        })

    return classifications


def format_corner_classifications(classifications: list[dict]) -> str:
    """Render corner classification dicts as a structured text block for the API."""
    lines: list[str] = []
    lines.append(
        "IDEAL LAP NOTE: The ideal lap is the driver's own best sector compilation "
        "from this session. Every sector is a valid, demonstrated data point. "
        "Traffic-affected laps have been excluded from this analysis."
    )
    lines.append("")

    for cls in classifications:
        dist_str = f"{cls['corner_distance_m']:.0f}m" if cls["corner_distance_m"] is not None else "N/A"
        w_start = cls.get("window_start_m")
        w_end = cls.get("window_end_m")
        window_str = (
            f"{w_start:.0f}–{w_end:.0f}m" if w_start is not None and w_end is not None else "N/A"
        )
        lines.append(f"Corner name: {cls['corner_name']}  ← use this exact value for corner_name in your tool call")
        compare_lap = cls.get("compare_lap_number")
        lap_ref = f"Lap {compare_lap} (compare)" if compare_lap is not None else "N/A"
        lines.append(
            f"Corner: {cls['corner_name']} | Distance: {dist_str} | "
            f"Analysis window: {window_str} | Compare lap: {lap_ref}"
        )

        speed_str = f"{cls['driver_speed_mph']} mph" if cls["driver_speed_mph"] is not None else "N/A"
        source_lap = cls.get("ideal_source_lap_number")
        lines.append(f"Phase of interest: {cls['phase']}")
        # Only show speed delta when compare lap is not the ideal source lap
        if cls.get("speed_delta_mph") is not None and source_lap != cls.get("compare_lap_number"):
            delta_str = f"{cls['speed_delta_mph']:+.1f} mph"
            ideal_speed_str = f"{cls['ideal_speed_mph']} mph" if cls["ideal_speed_mph"] is not None else "N/A"
            lines.append(f"Speed at phase: {speed_str} | Ideal lap: {ideal_speed_str} | Delta: {delta_str}")
        else:
            lines.append(f"Speed at phase: {speed_str}")
        lines.append(f"Brake trace: {cls['brake_description']}")
        lines.append(f"Steering: {cls['steer_state']}")
        lines.append(f"Throttle: {cls['throttle_state']}")
        lines.append(f"Engine braking: {cls['engine_braking']}")
        lines.append(
            f"Classification: front axle {cls['front_axle_state']}, "
            f"deceleration needed {cls['decel_need']}, "
            f"{cls['handling_condition']}"
        )
        source_lap = cls.get("ideal_source_lap_number")
        compare_lap = cls.get("compare_lap_number")
        source_note = (
            f" (theoretical fastest — best sector from Lap {source_lap})"
            if source_lap is not None else " (theoretical fastest)"
        )
        lines.append(
            f"Sector delta: +{cls['avg_delta_ms']}ms vs theoretical fastest{source_note} | "
            f"Compare lap: Lap {compare_lap}"
        )
        lines.append("")

    return "\n".join(lines)


def format_corner_knowledge(
    knowledge_entries: list[dict],
    circuit_corners: list[dict] | None,
) -> str:
    """Render corner knowledge entries as a CORNER-SPECIFIC CONSTRAINTS block.

    Returns an empty string if there are no entries to inject.

    Designed to appear:
    - In Call 1 user message: prepended before corner classification blocks
    - In Call 2 system prompt: appended as additional hard constraints
    """
    if not knowledge_entries:
        return ""

    # Build corner lookup: corner_number → {name, distance_m}
    corner_map: dict[int, dict] = {}
    if circuit_corners:
        for c in circuit_corners:
            corner_map[int(c["corner_number"])] = c

    lines: list[str] = []
    lines.append("=" * 60)
    lines.append("CORNER-SPECIFIC CONSTRAINTS")
    lines.append("=" * 60)
    lines.append(
        "These constraints are derived from curated knowledge and driver feedback "
        "for this circuit. They are HARD RULES. Do not violate them regardless of "
        "what the telemetry suggests."
    )
    lines.append("")

    # Circuit-wide entries first (corner_number IS NULL)
    circuit_wide = [e for e in knowledge_entries if e.get("corner_number") is None]
    corner_specific = [e for e in knowledge_entries if e.get("corner_number") is not None]

    for entry in circuit_wide:
        lines.append("CIRCUIT-WIDE:")
        _append_knowledge_fields(lines, entry)
        lines.append("")

    # Group by corner_number
    from itertools import groupby
    corner_specific_sorted = sorted(corner_specific, key=lambda e: e["corner_number"])
    for cn, group in groupby(corner_specific_sorted, key=lambda e: e["corner_number"]):
        c_info = corner_map.get(int(cn))
        if c_info:
            name_part = f" ({c_info['name']})" if c_info.get("name") else ""
            dist_part = f" — @{c_info['distance_m']:.0f}m"
            header = f"T{cn}{name_part}{dist_part}:"
        else:
            header = f"T{cn}:"
        lines.append(header)
        for entry in group:
            _append_knowledge_fields(lines, entry)
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


def _append_knowledge_fields(lines: list[str], entry: dict) -> None:
    """Append non-null knowledge fields as indented lines."""
    if entry.get("typical_phase_of_interest"):
        lines.append(f"  Phase: {entry['typical_phase_of_interest']}")
    if entry.get("known_handling_tendency"):
        lines.append(f"  Known tendency: {entry['known_handling_tendency']}")
    if entry.get("correct_technique"):
        lines.append(f"  Correct technique: {entry['correct_technique']}")
    incorrect = entry.get("incorrect_recommendations")
    if incorrect:
        recs = incorrect if isinstance(incorrect, list) else []
        if recs:
            lines.append(f"  NEVER recommend: {', '.join(recs)}")
    if entry.get("coaching_notes"):
        lines.append(f"  Notes: {entry['coaching_notes']}")
    if entry.get("source") == "correction":
        lines.append("  [Source: driver correction — treated as ground truth]")


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
        compare_lap_num = ws.get("compare_lap_number")
        ideal_source_lap = ws.get("ideal_source_lap_number")

        delta_to_ideal = driver_best_ms - ideal_sector_ms

        lines.append(f"\n--- Sector #{i}: Sector {sector_num} (Lap {compare_lap_num}) ---")
        lines.append(f"  Compare lap sector time:    {driver_best_ms:,} ms ({driver_best_ms/1000:.3f}s)")
        lines.append(f"  Theoretical fastest:        {ideal_sector_ms:,} ms ({ideal_sector_ms/1000:.3f}s)")
        lines.append(f"  Delta to theoretical:       +{delta_to_ideal:,} ms (+{delta_to_ideal/1000:.3f}s)")

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
        trace_lap_label = f"Lap {compare_lap_num}" if compare_lap_num is not None else "compare lap"
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
