"""VBOAdapter — parses VBOX / RaceChrono .vbo telemetry files into TelemetryFrame objects."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Iterator

from app.adapters.base import (
    TelemetryAdapter,
    TelemetryFrame,
    haversine_m,
    register_adapter,
)

# ---------------------------------------------------------------------------
# Synonym table: VBO column name → canonical field name
# ---------------------------------------------------------------------------

_SYNONYMS: dict[str, str] = {
    # timestamp
    "time": "time_s",
    "utc time": "time_s",
    # satellites
    "satellites": "satellites",
    "satellite count": "satellites",
    "sats": "satellites",
    # position
    "latitude": "lat",
    "lat": "lat",
    "longitude": "lon",
    "long": "lon",
    # speed
    "velocity kmh": "speed_kph",
    "velocity-calc kmh": "speed_kph",
    "velocity": "speed_kph",
    "velocity-calc": "speed_kph",
    "speed": "speed_kph",
    "velocity-obd kmh": "speed_obd_kph",   # secondary — only used if primary absent
    "velocity-obd": "speed_obd_kph",
    # heading
    "heading": "heading_deg",
    "bearing": "heading_deg",
    # altitude
    "height": "altitude_m",
    "altitude": "altitude_m",
    # lateral G
    "lateral-g": "lat_g",
    "lateral g": "lat_g",
    "lat-g": "lat_g",
    "latacc-calc": "lat_g",
    "latacc-calc g": "lat_g",
    "lateral_acc": "lat_g",
    # longitudinal G
    "longitudinal-g": "lon_g",
    "long-g": "lon_g",
    "longitudinal g": "lon_g",
    "longacc-calc": "lon_g",
    "longacc-calc g": "lon_g",
    "longitudinal_acc": "lon_g",
    "long accel g": "lon_g",
    "lat accel g": "lat_g",
    # throttle
    "throttle": "throttle_pct",
    "throttle pos": "throttle_pct",
    "throttle_pos": "throttle_pct",
    "throttle_pos-obd": "throttle_pct",
    "throttle pos-obd": "throttle_pct",
    # brake
    "brake": "brake_pct",
    "brake pos": "brake_pct",
    "brake_pos": "brake_pct",
    "brake_pos-obd": "brake_pct",
    "brake pos-obd": "brake_pct",
    # steering
    "steer angle": "steering_deg",
    "steering angle": "steering_deg",
    # gear
    "gear": "gear",
    # rpm
    "rpm": "rpm",
    "engine rpm": "rpm",
    "rpm-obd": "rpm",
    # hdop / accuracy
    "hdop": "hdop",
    "accuracy": "hdop",
    # wall-time helpers
    "utcdate": "utcdate",
    "utctime": "utctime",
}


def _canonical(raw_name: str) -> str | None:
    """Return the canonical field name for *raw_name*, or None if not known."""
    return _SYNONYMS.get(raw_name.strip().lower())


# ---------------------------------------------------------------------------
# Section parser
# ---------------------------------------------------------------------------

def _parse_sections(text: str) -> dict[str, list[str]]:
    """Split a VBO file into named sections."""
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].lower()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
    return sections


# ---------------------------------------------------------------------------
# Coordinate conversion: arcminutes → decimal degrees
# ---------------------------------------------------------------------------
# RaceChrono VBO stores coordinates as total arcminutes (not DDMM.MMMM).
# e.g. lat "+2354.302097" = 2354.302097 / 60 = 39.238368°N
#      lon "+04678.133011" = -(4678.133011 / 60) = -77.968884°W
# Sign of lat is explicit (+N, would be - for S).
# Sign of lon is always positive in the file; West is determined by geography.
# We detect West longitude by checking if abs value / 60 > 90 (can't be lat)
# and the session is in the western hemisphere (negative lon expected).
# Simpler: we pass the raw sign through and let the caller handle hemisphere.

def _arcmin_to_decimal(value: str) -> float | None:
    """
    Convert RaceChrono arcminute coordinate to decimal degrees.
    The sign in the raw value encodes N/S for lat; for lon the file uses positive
    values even for Western hemisphere — callers must apply the correct sign.
    """
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None
    return v / 60.0


def _is_arcminutes(value: str) -> bool:
    """Heuristic: is this coordinate stored as arcminutes (RaceChrono format)?"""
    try:
        v = abs(float(value))
        # Decimal degrees: lat ≤ 90, lon ≤ 180.
        # Arcminute values: lat ~0–5400, lon ~0–10800.
        # If abs value > 180 it must be arcminutes.
        return v > 180
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Time parsing: HHMMSS.SS → seconds from midnight
# ---------------------------------------------------------------------------

def _hhmmss_to_seconds(value: str) -> float | None:
    """
    Convert HHMMSS.SS format to seconds from midnight.
    e.g. "152648.66" → 15*3600 + 26*60 + 48.66 = 55728.66
    """
    try:
        v = float(value)
    except (ValueError, TypeError):
        return None

    # If value looks like HHMMSS.SS (6+ digits before decimal)
    int_part = int(v)
    frac = v - int_part

    if int_part >= 10000:  # HHMMSS format
        hh = int_part // 10000
        mm = (int_part % 10000) // 100
        ss = int_part % 100
        return hh * 3600 + mm * 60 + ss + frac

    # Already looks like plain seconds
    return v


# ---------------------------------------------------------------------------
# Wall-time parser
# ---------------------------------------------------------------------------

_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_TIME_RE = re.compile(r"(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?")


def _parse_wall_time(date_str: str, time_str: str) -> datetime | None:
    dm = _DATE_RE.match(date_str.strip())
    tm = _TIME_RE.match(time_str.strip())
    if not dm or not tm:
        return None
    try:
        day, month, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
        hour, minute, second = int(tm.group(1)), int(tm.group(2)), int(tm.group(3))
        frac = tm.group(4) or "0"
        microsecond = int(frac.ljust(6, "0")[:6])
        return datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone.utc)
    except (ValueError, OverflowError):
        return None


# ---------------------------------------------------------------------------
# VBOAdapter
# ---------------------------------------------------------------------------

@register_adapter
class VBOAdapter(TelemetryAdapter):
    FORMAT_ID = "vbo"
    SUPPORTED_EXTENSIONS = (".vbo",)

    @classmethod
    def detect(cls, file_bytes: bytes) -> bool:
        header = file_bytes[:4096]
        # Require [header] and [column names] — RaceChrono may omit [channel setup]
        return b"[header]" in header and b"[column names]" in header

    def session_metadata(self, file_bytes: bytes) -> dict:
        text = file_bytes.decode("latin-1", errors="replace")
        sections = _parse_sections(text)
        meta: dict = {"format": "vbo"}
        for line in sections.get("channel setup", []):
            if line.lower().startswith("frequency="):
                try:
                    meta["sample_rate_hz"] = float(line.split("=", 1)[1])
                except ValueError:
                    pass
        # RaceChrono stores session name in [session data]
        for line in sections.get("session data", []):
            if line.lower().startswith("name "):
                meta["session_name"] = line[5:].strip()
        meta["header_lines"] = sections.get("header", [])
        return meta

    def parse(self, file_bytes: bytes) -> Iterator[TelemetryFrame]:
        text = file_bytes.decode("latin-1", errors="replace")
        sections = _parse_sections(text)

        col_names_raw = sections.get("column names", [])
        if not col_names_raw:
            return

        columns_raw = " ".join(col_names_raw).split()
        col_index: dict[str, int] = {}
        for i, raw in enumerate(columns_raw):
            canon = _canonical(raw)
            if canon and canon not in col_index:
                col_index[canon] = i
            # secondary speed fallback
            if canon == "speed_obd_kph" and "speed_kph" not in col_index:
                col_index["speed_kph"] = i

        data_lines = sections.get("data", [])

        # Detect coordinate and time format from first valid data line
        use_arcmin: bool = False
        use_hhmmss: bool = False
        lon_is_positive_west: bool = False  # RaceChrono stores W lon as positive
        for line in data_lines:
            if not line or line.startswith(";"):
                continue
            parts = line.split()
            lat_idx = col_index.get("lat")
            lon_idx = col_index.get("lon")
            time_idx = col_index.get("time_s")
            if lat_idx is not None and lat_idx < len(parts):
                use_arcmin = _is_arcminutes(parts[lat_idx])
            if lon_idx is not None and lon_idx < len(parts) and use_arcmin:
                # If arcminutes lon/60 > 90 it cannot be a valid longitude in decimal,
                # so it must need negation for western hemisphere.
                # We detect western hemisphere: if lon/60 is between 60 and 180 and
                # the session lat suggests Americas/Europe, apply negative.
                try:
                    lon_val = abs(float(parts[lon_idx])) / 60.0
                    # Longitudes in western hemisphere (Americas) are negative.
                    # RaceChrono stores them as positive arcminutes.
                    # Heuristic: if lon_val > 0 and lat suggests N. America/Europe
                    # we negate. Since lon arcmin values are always > 0 in file,
                    # we check if the value looks like a western longitude (30-180°W).
                    if 30 < lon_val <= 180:
                        lon_is_positive_west = True
                except ValueError:
                    pass
            if time_idx is not None and time_idx < len(parts):
                try:
                    v = float(parts[time_idx])
                    use_hhmmss = v > 10000  # HHMMSS values are large numbers
                except ValueError:
                    pass
            break

        prev_lat: float | None = None
        prev_lon: float | None = None
        cumulative_distance_m: float = 0.0
        base_time_s: float | None = None

        for line in data_lines:
            if not line or line.startswith(";"):
                continue
            parts = line.split()
            if not parts:
                continue

            def _get(field: str):
                idx = col_index.get(field)
                if idx is None or idx >= len(parts):
                    return None
                return parts[idx]

            def _float(field: str, default: float | None = None) -> float | None:
                v = _get(field)
                if v is None:
                    return default
                try:
                    return float(v)
                except ValueError:
                    return default

            def _int(field: str, default: int | None = None) -> int | None:
                v = _float(field)
                return int(v) if v is not None else default

            # Position
            lat_raw = _get("lat")
            lon_raw = _get("lon")
            if lat_raw is None or lon_raw is None:
                continue

            if use_arcmin:
                lat = _arcmin_to_decimal(lat_raw)
                lon = _arcmin_to_decimal(lon_raw)
                if lon is not None and lon_is_positive_west:
                    lon = -lon
            else:
                try:
                    lat = float(lat_raw)
                    lon = float(lon_raw)
                except ValueError:
                    continue

            if lat is None or lon is None:
                continue

            # Timestamp
            time_raw = _get("time_s")
            time_s: float = 0.0
            if time_raw is not None:
                if use_hhmmss:
                    parsed = _hhmmss_to_seconds(time_raw)
                    if parsed is not None:
                        if base_time_s is None:
                            base_time_s = parsed
                        time_s = parsed - base_time_s
                else:
                    try:
                        time_s = float(time_raw)
                    except ValueError:
                        time_s = 0.0

            timestamp_ms = int(time_s * 1000)

            # Distance
            if prev_lat is not None and prev_lon is not None:
                cumulative_distance_m += haversine_m(prev_lat, prev_lon, lat, lon)
            prev_lat, prev_lon = lat, lon

            # Wall time
            wall_time: datetime | None = None
            date_val = _get("utcdate")
            time_val = _get("utctime")
            if date_val and time_val:
                wall_time = _parse_wall_time(date_val, time_val)

            # Speed: use logged value if non-zero, else derive from GPS distance/time delta
            logged_speed = _float("speed_kph", 0.0) or 0.0
            if logged_speed == 0.0 and prev_lat is not None and timestamp_ms > 0:
                # GPS-derived speed from haversine delta
                dt_s = (timestamp_ms - getattr(self, '_prev_ts_ms', 0)) / 1000.0
                if dt_s > 0:
                    step_m = haversine_m(prev_lat, prev_lon, lat, lon)
                    logged_speed = (step_m / dt_s) * 3.6
            self._prev_ts_ms = timestamp_ms  # type: ignore[attr-defined]

            yield TelemetryFrame(
                timestamp_ms=timestamp_ms,
                wall_time=wall_time,
                distance_m=cumulative_distance_m,
                lat=lat,
                lon=lon,
                speed_kph=logged_speed,
                throttle_pct=_float("throttle_pct"),
                brake_pct=_float("brake_pct"),
                steering_deg=_float("steering_deg"),
                gear=_int("gear"),
                rpm=_int("rpm"),
                lat_g=_float("lat_g"),
                lon_g=_float("lon_g"),
                altitude_m=_float("altitude_m"),
                heading_deg=_float("heading_deg"),
                hdop=_float("hdop"),
                satellites=_int("satellites"),
                lap_number=None,
                raw_channel_data={
                    columns_raw[i]: parts[i]
                    for i in range(min(len(columns_raw), len(parts)))
                },
            )
