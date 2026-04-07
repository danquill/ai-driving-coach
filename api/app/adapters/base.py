"""Base adapter types: TelemetryFrame dataclass, TelemetryAdapter ABC, haversine helper."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Iterator


# ---------------------------------------------------------------------------
# Haversine distance helper
# ---------------------------------------------------------------------------

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance in metres between two WGS-84 points."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


# ---------------------------------------------------------------------------
# Canonical telemetry frame
# ---------------------------------------------------------------------------

@dataclass
class TelemetryFrame:
    timestamp_ms: int               # milliseconds from session start
    wall_time: datetime | None      # absolute UTC time if available
    distance_m: float
    lat: float
    lon: float
    speed_kph: float
    throttle_pct: float | None
    brake_pct: float | None
    steering_deg: float | None
    gear: int | None
    rpm: int | None
    lat_g: float | None
    lon_g: float | None
    altitude_m: float | None
    heading_deg: float | None
    hdop: float | None
    satellites: int | None
    lap_number: int | None = None   # always None at parse time
    raw_channel_data: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Exception
# ---------------------------------------------------------------------------

class UnsupportedFormatError(Exception):
    """Raised when no adapter can handle the given file."""


# ---------------------------------------------------------------------------
# Abstract base adapter
# ---------------------------------------------------------------------------

class TelemetryAdapter(ABC):
    FORMAT_ID: ClassVar[str]
    SUPPORTED_EXTENSIONS: ClassVar[tuple[str, ...]]

    @classmethod
    @abstractmethod
    def detect(cls, file_bytes: bytes) -> bool:
        """Return True if this adapter can handle *file_bytes*."""

    @abstractmethod
    def parse(self, file_bytes: bytes) -> Iterator[TelemetryFrame]:
        """Yield TelemetryFrame objects parsed from *file_bytes*."""

    @abstractmethod
    def session_metadata(self, file_bytes: bytes) -> dict:
        """Return a dict of session-level metadata from the file header."""


# ---------------------------------------------------------------------------
# Adapter registry + resolver
# ---------------------------------------------------------------------------

_REGISTRY: list[type[TelemetryAdapter]] = []


def register_adapter(cls: type[TelemetryAdapter]) -> type[TelemetryAdapter]:
    """Decorator that registers an adapter class."""
    _REGISTRY.append(cls)
    return cls


def resolve_adapter(file_bytes: bytes, filename: str) -> TelemetryAdapter:
    """
    Return an instantiated adapter for *file_bytes* / *filename*.

    Strategy:
    1. Try each registered adapter (except CSVAdapter) in order via detect().
    2. If none match, fall back to CSVAdapter.
    3. If CSVAdapter also rejects, raise UnsupportedFormatError.
    """
    from app.adapters.csv import CSVAdapter  # imported lazily to avoid circular

    non_csv = [a for a in _REGISTRY if a is not CSVAdapter]
    csv_adapters = [a for a in _REGISTRY if a is CSVAdapter]

    for adapter_cls in non_csv:
        if adapter_cls.detect(file_bytes):
            return adapter_cls()

    for adapter_cls in csv_adapters:
        if adapter_cls.detect(file_bytes):
            return adapter_cls()

    raise UnsupportedFormatError(
        f"No adapter found for file '{filename}'. "
        f"Supported extensions: vbo, csv."
    )
