"""Adapter package — exports public API."""

from app.adapters.base import (
    TelemetryAdapter,
    TelemetryFrame,
    UnsupportedFormatError,
    haversine_m,
    resolve_adapter,
)

# Import concrete adapters to trigger @register_adapter side-effects
from app.adapters.vbo import VBOAdapter  # noqa: F401
from app.adapters.csv import CSVAdapter  # noqa: F401
from app.adapters.apex import ApexAdapter  # noqa: F401

__all__ = [
    "TelemetryAdapter",
    "TelemetryFrame",
    "UnsupportedFormatError",
    "haversine_m",
    "resolve_adapter",
    "VBOAdapter",
    "CSVAdapter",
    "ApexAdapter",
]
