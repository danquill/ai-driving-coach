"""ApexAdapter — parses Apex Pro .apexSession files (JSON + binary-encoded rows).

File structure:
  Single JSON object with:
    apexData   — list of base64 strings, each 168 bytes = 21 little-endian doubles
    obdiiData  — list of base64 strings, each 160 bytes = 20 little-endian doubles
    lapIndex   — list of integer row indices where each lap boundary occurs
    lapTimes   — list of lap times in seconds
    sessionDate — Apple CoreData epoch (seconds since 2001-01-01 00:00:00 UTC)

apexData double layout (21 × 8 = 168 bytes):
  [0]  unknown
  [1]  unknown
  [2]  time — Apple CoreData epoch seconds (10 Hz)
  [3..11] various (gyro/filter artifacts — unreliable)
  [12] longitude (decimal degrees, negative = West)
  [13] latitude  (decimal degrees)
  [14..20] various (altitude artifacts — unreliable)

apexData float layout (42 × 4 = 168 bytes, overlaid on the same bytes):
  [12] lateral G      (positive = right)
  [13] longitudinal G (negative = braking)
  [14] vertical G     (~-1.0 at rest)

obdiiData double layout (20 × 8 = 160 bytes):
  [0] timestamp — Apple CoreData epoch seconds
  [1] speed (mph)
  [2] RPM
  [3] speed (kph, sometimes zero/noisy — prefer d[1]*1.60934)
  [4] intake manifold pressure (PSI)
  [5] throttle position (%)
  [6..] other OBD channels (coolant/IAT temps etc.)
"""

from __future__ import annotations

import base64
import json
import struct
from datetime import datetime, timezone
from typing import Iterator

from app.adapters.base import (
    TelemetryAdapter,
    TelemetryFrame,
    haversine_m,
    register_adapter,
)

# Apple CoreData epoch: 2001-01-01 00:00:00 UTC as Unix timestamp
_APPLE_EPOCH_OFFSET = 978307200.0

# apexData struct: 21 little-endian doubles
_APEX_FMT = "<21d"
_APEX_SIZE = 21 * 8  # 168

# apexData as floats for G channels
_APEX_FLOAT_FMT = "<42f"

# obdiiData struct: 20 little-endian doubles
_OBD_FMT = "<20d"
_OBD_SIZE = 20 * 8  # 160


def _decode_apex(row: str) -> tuple[list[float], list[float]] | None:
    """Return (doubles, floats) for an apex row, or None on error."""
    try:
        raw = base64.b64decode(row)
        if len(raw) != _APEX_SIZE:
            return None
        return list(struct.unpack(_APEX_FMT, raw)), list(struct.unpack(_APEX_FLOAT_FMT, raw))
    except Exception:
        return None


def _decode_obd(row: str) -> list[float] | None:
    """Return doubles for an OBD row, or None on error."""
    try:
        raw = base64.b64decode(row)
        if len(raw) != _OBD_SIZE:
            return None
        return list(struct.unpack(_OBD_FMT, raw))
    except Exception:
        return None


def _apple_to_unix(ts: float) -> float:
    """Convert Apple CoreData epoch to Unix epoch."""
    return ts + _APPLE_EPOCH_OFFSET


@register_adapter
class ApexAdapter(TelemetryAdapter):
    FORMAT_ID = "apexsession"
    SUPPORTED_EXTENSIONS = (".apexsession",)

    @classmethod
    def detect(cls, file_bytes: bytes) -> bool:
        try:
            # Quick sniff: must be JSON with apexData and obdiiData keys
            head = file_bytes[:256].decode("utf-8", errors="replace")
            if '"apexData"' not in head and b'"apexData"' not in file_bytes[:4096]:
                return False
            data = json.loads(file_bytes)
            return "apexData" in data and "obdiiData" in data
        except Exception:
            return False

    def session_metadata(self, file_bytes: bytes) -> dict:
        try:
            data = json.loads(file_bytes)
        except Exception:
            return {"format": "apexsession"}

        meta: dict = {"format": "apexsession"}
        if data.get("trackName"):
            meta["session_name"] = data["trackName"]
        if data.get("sessionDate"):
            unix_ts = _apple_to_unix(float(data["sessionDate"]))
            meta["recorded_at"] = datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()
        return meta

    def parse(self, file_bytes: bytes) -> Iterator[TelemetryFrame]:
        try:
            data = json.loads(file_bytes)
        except Exception:
            return

        apex_rows: list[str] = data.get("apexData") or []
        obd_rows: list[str] = data.get("obdiiData") or []
        if not apex_rows:
            return

        # Build OBD lookup by row index (same length as apex_rows)
        # OBD rows align 1:1 with apex rows
        n = len(apex_rows)

        # Determine session base time from the first valid apex row
        base_unix: float | None = None
        for row in apex_rows[:20]:
            decoded = _decode_apex(row)
            if decoded:
                ts = decoded[0][2]
                if ts > 0:
                    base_unix = _apple_to_unix(ts)
                    break

        prev_lat: float | None = None
        prev_lon: float | None = None
        cumulative_distance_m: float = 0.0

        for i in range(n):
            apex_dec = _decode_apex(apex_rows[i])
            if apex_dec is None:
                continue
            doubles, floats = apex_dec

            lat = doubles[13]
            lon = doubles[12]
            if lat == 0.0 and lon == 0.0:
                continue
            # Sanity-check coordinate range
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                continue

            apex_time = doubles[2]
            if apex_time <= 0:
                continue

            unix_ts = _apple_to_unix(apex_time)
            if base_unix is None:
                base_unix = unix_ts

            session_s = unix_ts - base_unix
            timestamp_ms = int(session_s * 1000)

            # Distance
            if prev_lat is not None and prev_lon is not None:
                cumulative_distance_m += haversine_m(prev_lat, prev_lon, lat, lon)
            prev_lat, prev_lon = lat, lon

            # G forces from the float overlay
            lat_g = floats[12] if abs(floats[12]) < 5 else None
            lon_g = floats[13] if abs(floats[13]) < 5 else None

            # Wall time
            wall_time = datetime.fromtimestamp(unix_ts, tz=timezone.utc)

            # OBD channels
            speed_kph: float = 0.0
            rpm: int | None = None
            throttle_pct: float | None = None

            if i < len(obd_rows):
                obd_dec = _decode_obd(obd_rows[i])
                if obd_dec:
                    speed_mph = obd_dec[1]
                    if speed_mph > 0:
                        speed_kph = speed_mph * 1.60934
                    obd_rpm = obd_dec[2]
                    if obd_rpm > 0:
                        rpm = int(obd_rpm)
                    thr = obd_dec[5]
                    if 0 <= thr <= 100:
                        throttle_pct = thr

            yield TelemetryFrame(
                timestamp_ms=timestamp_ms,
                wall_time=wall_time,
                distance_m=cumulative_distance_m,
                lat=lat,
                lon=lon,
                speed_kph=speed_kph,
                throttle_pct=throttle_pct,
                brake_pct=None,   # not available in OBDII
                steering_deg=None,
                gear=None,
                rpm=rpm,
                lat_g=lat_g,
                lon_g=lon_g,
                altitude_m=None,
                heading_deg=None,
                hdop=None,
                satellites=None,
                lap_number=None,
                raw_channel_data={
                    "apex_time": apex_time,
                    "lat": lat,
                    "lon": lon,
                    "lat_g": lat_g,
                    "lon_g": lon_g,
                    "speed_kph": speed_kph,
                    "rpm": rpm,
                    "throttle_pct": throttle_pct,
                },
            )
