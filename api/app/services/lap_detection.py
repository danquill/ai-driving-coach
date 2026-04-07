"""Lap detection service — GPS-based haversine + heading with debounce."""

from __future__ import annotations

import math
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Haversine helper (also in adapters/base.py, duplicated here to keep service
# layer self-contained and usable from both API and worker)
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


def _heading_diff(a: float, b: float) -> float:
    """Return absolute angular difference between two headings (0-360), max 180."""
    return abs((a - b + 180) % 360 - 180)


# ---------------------------------------------------------------------------
# detect_laps
# ---------------------------------------------------------------------------


def detect_laps(
    samples: list[dict],
    circuit: dict,
) -> list[dict]:
    """
    Detect lap boundaries from GPS telemetry samples.

    Args:
        samples: rows from telemetry_samples, each with keys:
                 time (datetime), lat, lon, speed_kph, heading_deg, distance_m
        circuit: dict with keys:
                 start_finish_lat, start_finish_lon, start_finish_heading_deg,
                 geofence_radius_m

    Returns:
        List of dicts: {lap_number, start_time, end_time, lap_time_ms,
                        is_outlap, is_inlap}
    """
    if not samples:
        return []

    if circuit.get("start_finish_lat") is None or circuit.get("start_finish_lon") is None:
        raise ValueError(
            "Circuit has no start/finish coordinates. "
            "Import a lap from the circuit editor to set the track geometry and start/finish point."
        )
    sf_lat = float(circuit["start_finish_lat"])
    sf_lon = float(circuit["start_finish_lon"])
    sf_heading = float(circuit["start_finish_heading_deg"] or 0)
    radius_m = float(circuit["geofence_radius_m"] or 50)
    exit_radius_m = radius_m * 1.5

    # Sort samples by time to be safe
    sorted_samples = sorted(samples, key=lambda s: s["time"])

    crossings: list[datetime] = []
    inside_fence = False
    exited_after_last_crossing = True  # allow first crossing immediately

    for sample in sorted_samples:
        lat = sample.get("lat")
        lon = sample.get("lon")
        heading = sample.get("heading_deg")

        if lat is None or lon is None:
            continue

        dist = _haversine_m(lat, lon, sf_lat, sf_lon)

        if dist < radius_m:
            if not inside_fence:
                inside_fence = True
                # Check heading constraint (skip if heading unavailable)
                if heading is not None:
                    hdiff = _heading_diff(float(heading), sf_heading)
                    if hdiff > 45:
                        # Wrong direction — mark as inside fence but don't trigger
                        # Don't skip: still need to fall through to exit detection below
                        pass
                    elif exited_after_last_crossing:
                        crossings.append(sample["time"])
                        exited_after_last_crossing = False
                elif exited_after_last_crossing:
                    # No heading data — trigger on any crossing
                    crossings.append(sample["time"])
                    exited_after_last_crossing = False
        else:
            inside_fence = False
            if dist > exit_radius_m:
                exited_after_last_crossing = True

    if not crossings:
        # No crossings detected — entire session is one outlap
        return []

    laps: list[dict] = []

    # Everything before first crossing = outlap (lap_number=0)
    first_crossing = crossings[0]
    session_start = sorted_samples[0]["time"]
    session_end = sorted_samples[-1]["time"]

    # Build lap list
    # Lap 0: outlap (from session start to first crossing)
    outlap_ms = int((first_crossing - session_start).total_seconds() * 1000)
    laps.append({
        "lap_number": 0,
        "start_time": session_start,
        "end_time": first_crossing,
        "lap_time_ms": outlap_ms,
        "is_outlap": True,
        "is_inlap": False,
    })

    # Full laps: consecutive crossings
    for i in range(len(crossings) - 1):
        start = crossings[i]
        end = crossings[i + 1]
        lap_ms = int((end - start).total_seconds() * 1000)
        laps.append({
            "lap_number": i + 1,
            "start_time": start,
            "end_time": end,
            "lap_time_ms": lap_ms,
            "is_outlap": False,
            "is_inlap": False,
        })

    # Last incomplete lap (from last crossing to session end) = inlap
    last_crossing = crossings[-1]
    if last_crossing < session_end:
        inlap_ms = int((session_end - last_crossing).total_seconds() * 1000)
        laps.append({
            "lap_number": len(crossings),
            "start_time": last_crossing,
            "end_time": session_end,
            "lap_time_ms": inlap_ms,
            "is_outlap": False,
            "is_inlap": True,
        })

    return laps


# ---------------------------------------------------------------------------
# assign_lap_numbers
# ---------------------------------------------------------------------------


def assign_lap_numbers(
    samples: list[dict],
    laps: list[dict],
) -> list[dict]:
    """
    Assign lap_number to each sample based on which lap's time window it falls in.

    Args:
        samples: list of sample dicts (with 'time' key)
        laps: output of detect_laps

    Returns:
        Same sample dicts with 'lap_number' key filled in (None if not in any lap).
    """
    if not laps:
        for s in samples:
            s["lap_number"] = None
        return samples

    # Sort laps by start_time for binary search
    sorted_laps = sorted(laps, key=lambda l: l["start_time"])

    for sample in samples:
        t = sample["time"]
        assigned = None
        for lap in sorted_laps:
            if lap["start_time"] <= t < lap["end_time"]:
                assigned = lap["lap_number"]
                break
        sample["lap_number"] = assigned

    return samples
