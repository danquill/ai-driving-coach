"""Sector crossing detection and sector time computation."""

from __future__ import annotations

import math
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Haversine helper (self-contained copy)
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# detect_sector_crossings
# ---------------------------------------------------------------------------


def detect_sector_crossings(
    samples: list[dict],
    sectors: list[dict],
    lap_start_time: datetime,
    lap_end_time: datetime,
) -> list[dict]:
    """
    Find the point in telemetry samples where the car crosses each sector trigger.

    Args:
        samples: telemetry samples for ONE lap, each with:
                 time (datetime), lat, lon, speed_kph
        sectors: circuit_sectors rows, each with:
                 sector_number, trigger_lat, trigger_lon, trigger_heading_deg
        lap_start_time: datetime start of the lap
        lap_end_time: datetime end of the lap

    Returns:
        List of dicts: {sector_number, crossing_time, entry_speed_kph, exit_speed_kph}
    """
    if not samples or not sectors:
        return []

    # Filter samples to this lap's time window
    lap_samples = [
        s for s in samples
        if lap_start_time <= s["time"] <= lap_end_time
    ]
    if not lap_samples:
        return []

    sorted_samples = sorted(lap_samples, key=lambda s: s["time"])

    crossings = []
    for sector in sorted(sectors, key=lambda s: s["sector_number"]):
        trig_lat = float(sector["trigger_lat"])
        trig_lon = float(sector["trigger_lon"])

        # Find sample with minimum haversine distance to trigger point
        best_sample = min(
            (s for s in sorted_samples if s.get("lat") is not None and s.get("lon") is not None),
            key=lambda s: _haversine_m(float(s["lat"]), float(s["lon"]), trig_lat, trig_lon),
            default=None,
        )

        if best_sample is None:
            continue

        crossing_time = best_sample["time"]

        # Entry speed: sample ~2 seconds before crossing
        target_entry = crossing_time - timedelta(seconds=2)
        entry_sample = min(
            sorted_samples,
            key=lambda s: abs((s["time"] - target_entry).total_seconds()),
        )
        entry_speed = entry_sample.get("speed_kph")

        # Exit speed: sample ~2 seconds after crossing
        target_exit = crossing_time + timedelta(seconds=2)
        exit_sample = min(
            sorted_samples,
            key=lambda s: abs((s["time"] - target_exit).total_seconds()),
        )
        exit_speed = exit_sample.get("speed_kph")

        crossings.append({
            "sector_number": int(sector["sector_number"]),
            "crossing_time": crossing_time,
            "entry_speed_kph": float(entry_speed) if entry_speed is not None else None,
            "exit_speed_kph": float(exit_speed) if exit_speed is not None else None,
        })

    # Sort by crossing_time to ensure correct order
    crossings.sort(key=lambda c: c["crossing_time"])
    return crossings


# ---------------------------------------------------------------------------
# compute_sector_times
# ---------------------------------------------------------------------------


def compute_sector_times(
    crossings: list[dict],
    lap_start_time: datetime,
    lap_end_time: datetime,
    lap_time_ms: int,
) -> list[dict]:
    """
    Compute sector times from crossing events.

    Sector time = time delta between consecutive crossings.
    First sector starts from lap_start_time.
    Last sector ends at lap_end_time.

    Args:
        crossings: output of detect_sector_crossings
        lap_start_time: datetime
        lap_end_time: datetime
        lap_time_ms: total lap time in ms

    Returns:
        List of dicts: {sector_number, sector_time_ms, entry_speed_kph, exit_speed_kph}
    """
    if not crossings:
        return []

    # Sort by sector_number
    sorted_crossings = sorted(crossings, key=lambda c: c["sector_number"])

    sector_times = []
    for i, crossing in enumerate(sorted_crossings):
        if i == 0:
            start_time = lap_start_time
        else:
            start_time = sorted_crossings[i - 1]["crossing_time"]

        if i == len(sorted_crossings) - 1:
            end_time = lap_end_time
        else:
            end_time = crossing["crossing_time"]

        sector_ms = int((end_time - start_time).total_seconds() * 1000)

        sector_times.append({
            "sector_number": crossing["sector_number"],
            "sector_time_ms": sector_ms,
            "entry_speed_kph": crossing["entry_speed_kph"],
            "exit_speed_kph": crossing["exit_speed_kph"],
        })

    return sector_times
