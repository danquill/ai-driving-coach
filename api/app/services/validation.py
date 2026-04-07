"""Data validation layer for telemetry frames."""

from __future__ import annotations

from app.adapters.base import TelemetryFrame, haversine_m

_MAX_HDOP = 5.0
_MIN_SATELLITES = 4
_GPS_TELEPORT_SPEED_KPH = 400.0   # implied speed threshold for dropout detection
_GPS_REPORTER_SPEED_KPH = 50.0    # if logger says < this, treat as dropout


def validate_frames(frames: list[TelemetryFrame]) -> list[TelemetryFrame]:
    """
    Clean and validate a list of TelemetryFrame objects.

    Steps:
    1. Sort by timestamp_ms.
    2. Filter poor GPS quality (hdop > 5, satellites < 4).
    3. Clamp throttle_pct and brake_pct to [0, 100].
    4. Remove GPS teleport dropouts.

    Returns the cleaned list.
    """
    if not frames:
        return frames

    # 1. Sort by timestamp
    frames = sorted(frames, key=lambda f: f.timestamp_ms)

    # 2. GPS quality filter
    filtered: list[TelemetryFrame] = []
    for f in frames:
        if f.hdop is not None and f.hdop > _MAX_HDOP:
            continue
        if f.satellites is not None and f.satellites < _MIN_SATELLITES:
            continue
        filtered.append(f)

    # 3. Clamp throttle/brake
    for f in filtered:
        if f.throttle_pct is not None:
            f.throttle_pct = max(0.0, min(100.0, f.throttle_pct))
        if f.brake_pct is not None:
            f.brake_pct = max(0.0, min(100.0, f.brake_pct))

    # 4. GPS teleport dropout detection
    cleaned: list[TelemetryFrame] = []
    for i, f in enumerate(filtered):
        if i == 0:
            cleaned.append(f)
            continue

        prev = filtered[i - 1]
        dt_s = (f.timestamp_ms - prev.timestamp_ms) / 1000.0
        if dt_s <= 0:
            cleaned.append(f)
            continue

        dist_m = haversine_m(prev.lat, prev.lon, f.lat, f.lon)
        implied_kph = (dist_m / dt_s) * 3.6

        if implied_kph > _GPS_TELEPORT_SPEED_KPH and f.speed_kph < _GPS_REPORTER_SPEED_KPH:
            # Likely a GPS dropout — skip this frame
            continue

        cleaned.append(f)

    return cleaned
