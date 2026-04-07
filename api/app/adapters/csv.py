"""CSVAdapter — generic CSV fallback adapter, handles RaceChrono and standard formats."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Iterator

from app.adapters.base import (
    TelemetryAdapter,
    TelemetryFrame,
    haversine_m,
    register_adapter,
)
from app.adapters.vbo import VBOAdapter, _SYNONYMS

# ---------------------------------------------------------------------------
# Extended synonym table for CSV column names
# ---------------------------------------------------------------------------

_CSV_SYNONYMS: dict[str, str] = {
    **_SYNONYMS,
    # RaceChrono CSV specific
    "timestamp": "time_s",
    "elapsed_time": "elapsed_s",
    "distance_traveled": "distance_m_col",
    "latitude": "lat",
    "longitude": "lon",
    "speed": "speed_kph",        # m/s in RaceChrono — converted below
    "bearing": "heading_deg",
    "altitude": "altitude_m",
    "accuracy": "hdop",
    "lateral_acc": "lat_g",
    "longitudinal_acc": "lon_g",
    "brake_pos": "brake_pct",
    "throttle_pos": "throttle_pct",
    "lap_number": "lap_number_col",
    "fragment_id": "_skip",
    "combined_acc": "_skip",
    "lean_angle": "_skip",
    "fix_type": "_skip",
    "device_update_rate": "_skip",
}


def _match_header(raw: str) -> str | None:
    key = raw.strip().lower()
    return _CSV_SYNONYMS.get(key) or _SYNONYMS.get(key)


# ---------------------------------------------------------------------------
# RaceChrono CSV: skip metadata lines to find the actual header row
# ---------------------------------------------------------------------------

def _find_header_row(lines: list[str]) -> int:
    """
    Return the index of the line that contains the actual column headers.
    RaceChrono CSVs have several metadata lines before the header row.
    We detect the header row as the first line that contains 'latitude' or 'lat'
    as a comma-separated token (case-insensitive).
    """
    for i, line in enumerate(lines):
        lower = line.lower()
        if "latitude" in lower or ",lat," in lower or lower.startswith("lat,"):
            return i
        # Also accept 'timestamp' as a known-good header indicator
        if lower.startswith("timestamp,"):
            return i
    return 0  # fallback: assume first line


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def _parse_timestamp(value: str) -> float | None:
    """Return epoch seconds (float) or None."""
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        pass
    # HH:MM:SS.fff
    try:
        parts = value.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
            return h * 3600 + m * 60 + s
    except (ValueError, IndexError):
        pass
    return None


# ---------------------------------------------------------------------------
# CSVAdapter
# ---------------------------------------------------------------------------

@register_adapter
class CSVAdapter(TelemetryAdapter):
    FORMAT_ID = "csv"
    SUPPORTED_EXTENSIONS = (".csv",)

    @classmethod
    def detect(cls, file_bytes: bytes) -> bool:
        if VBOAdapter.detect(file_bytes):
            return False
        text = file_bytes[:8192].decode("utf-8", errors="replace")
        lines = text.splitlines()
        header_idx = _find_header_row(lines)
        try:
            headers = next(csv.reader(io.StringIO(lines[header_idx])))
            matched = {_match_header(h) for h in headers} - {None, "_skip"}
            return "lat" in matched and "lon" in matched
        except Exception:
            return False

    def session_metadata(self, file_bytes: bytes) -> dict:
        text = file_bytes.decode("utf-8", errors="replace")
        meta: dict = {"format": "csv"}
        for line in text.splitlines()[:10]:
            if line.lower().startswith("session title,"):
                meta["session_name"] = line.split(",", 1)[1].strip().strip('"')
        return meta

    def parse(self, file_bytes: bytes) -> Iterator[TelemetryFrame]:
        text = file_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()

        header_idx = _find_header_row(lines)
        # Skip the header row itself plus any unit/source annotation rows
        # RaceChrono has: header row, units row, source row, then data
        # Detect and skip non-data rows after the header
        data_start = header_idx + 1
        for i in range(header_idx + 1, min(header_idx + 4, len(lines))):
            line = lines[i].strip()
            if not line:
                data_start = i + 1
                continue
            # If the first field doesn't parse as a number, it's a units/annotation row
            first_field = line.split(",")[0].strip().strip('"')
            try:
                float(first_field)
                data_start = i
                break
            except ValueError:
                data_start = i + 1

        header_line = lines[header_idx]
        data_lines = "\n".join(lines[data_start:])
        csv_text = header_line + "\n" + data_lines

        reader = csv.DictReader(io.StringIO(csv_text))
        if not reader.fieldnames:
            return

        # Build canonical → first matching csv header mapping
        # For duplicate column names, DictReader appends suffixes — we take the first match
        col_map: dict[str, str] = {}
        for raw_header in reader.fieldnames:
            # Strip DictReader's duplicate suffix (e.g. "speed.1", "speed.2")
            base = raw_header.split(".")[0] if "." in raw_header else raw_header
            canon = _match_header(base) or _match_header(raw_header)
            if canon and canon not in col_map and canon != "_skip":
                col_map[canon] = raw_header

        # Detect if speed column is in m/s (RaceChrono) vs kph
        # RaceChrono CSV header has a units row we already skipped,
        # but we can check the units line if present
        speed_is_ms = False
        if header_idx + 1 < len(lines):
            units_line = lines[header_idx + 1].lower()
            if "m/s" in units_line:
                speed_is_ms = True

        prev_lat: float | None = None
        prev_lon: float | None = None
        cumulative_distance_m: float = 0.0
        base_ts: float | None = None

        for row in reader:
            def _get(field: str) -> str:
                hdr = col_map.get(field)
                return row.get(hdr, "").strip() if hdr else ""

            def _float(field: str, default: float | None = None) -> float | None:
                v = _get(field)
                if not v:
                    return default
                try:
                    return float(v)
                except ValueError:
                    return default

            def _int(field: str, default: int | None = None) -> int | None:
                v = _float(field)
                return int(v) if v is not None else default

            # Position
            lat = _float("lat")
            lon = _float("lon")
            if lat is None or lon is None:
                continue

            # Timestamp — RaceChrono stores unix epoch seconds as float
            ts_raw = _get("time_s") or _get("elapsed_s")
            ts: float = 0.0
            if ts_raw:
                parsed = _parse_timestamp(ts_raw)
                if parsed is not None:
                    ts = parsed

            # Normalise to session-relative seconds
            if ts > 1_000_000_000:  # epoch seconds
                if base_ts is None:
                    base_ts = ts
                ts = ts - base_ts

            timestamp_ms = int(ts * 1000)

            # Distance — use provided column if available, else accumulate via haversine
            dist_col = _float("distance_m_col")
            if dist_col is not None:
                cumulative_distance_m = dist_col
            else:
                if prev_lat is not None and prev_lon is not None:
                    cumulative_distance_m += haversine_m(prev_lat, prev_lon, lat, lon)
            prev_lat, prev_lon = lat, lon

            # Speed: RaceChrono stores in m/s, convert to kph
            speed_raw = _float("speed_kph", 0.0) or 0.0
            speed_kph = speed_raw * 3.6 if speed_is_ms else speed_raw

            # Wall time from epoch timestamp
            wall_time: datetime | None = None
            if base_ts is not None and ts_raw:
                parsed_ts = _parse_timestamp(ts_raw)
                if parsed_ts and parsed_ts > 1_000_000_000:
                    wall_time = datetime.fromtimestamp(parsed_ts, tz=timezone.utc)

            yield TelemetryFrame(
                timestamp_ms=timestamp_ms,
                wall_time=wall_time,
                distance_m=cumulative_distance_m,
                lat=lat,
                lon=lon,
                speed_kph=speed_kph,
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
                lap_number=_int("lap_number_col"),
                raw_channel_data=dict(row),
            )
