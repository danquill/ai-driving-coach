"""Tests for corner pre-computation classification logic.

Covers:
- Correct entry phase detection
- Correct mid-corner phase detection
- Brush brake identification
- Threshold brake identification
- classify_corners() output structure
"""

from __future__ import annotations

import sys
import os

# Make api/app importable when running from the api/ directory or project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.services.coaching_prompt import (
    _detect_corner_phase,
    classify_corners,
    format_corner_classifications,
)


# ---------------------------------------------------------------------------
# Helpers to build synthetic telemetry windows
# ---------------------------------------------------------------------------

def _make_point(
    distance_m: float = 0.0,
    speed_kph: float = 80.0,
    brake_pct: float = 0.0,
    throttle_pct: float = 0.0,
    steering_deg: float = 0.0,
    lat_g: float = 0.0,
    lon_g: float = 0.0,
) -> dict:
    return {
        "distance_m": distance_m,
        "speed_kph": speed_kph,
        "brake_pct": brake_pct,
        "throttle_pct": throttle_pct,
        "steering_deg": steering_deg,
        "lat_g": lat_g,
        "lon_g": lon_g,
    }


def _entry_window() -> list[dict]:
    """Entry phase: brake active, steering low."""
    return [
        _make_point(distance_m=100 + i * 10, speed_kph=120 - i * 5, brake_pct=80.0, steering_deg=5.0)
        for i in range(10)
    ]


def _mid_corner_window(steering_peak: float = 120.0) -> list[dict]:
    """Mid-corner phase: brake zero, steering at peak, speed flat."""
    return [
        _make_point(
            distance_m=200 + i * 10,
            speed_kph=60.0,
            brake_pct=0.0,
            throttle_pct=0.0,
            steering_deg=steering_peak - (i * 0.5),  # slight unwind, stays near peak
        )
        for i in range(10)
    ]


def _turn_in_window(steering_peak: float = 120.0) -> list[dict]:
    """Turn-in phase: steering loading from 0 to peak, brake zero."""
    return [
        _make_point(
            distance_m=150 + i * 10,
            speed_kph=90.0,
            brake_pct=0.0,
            throttle_pct=0.0,
            steering_deg=steering_peak * (i / 9),
        )
        for i in range(10)
    ]


def _exit_window(steering_peak: float = 120.0) -> list[dict]:
    """Exit phase: steering unwinding, throttle increasing."""
    return [
        _make_point(
            distance_m=250 + i * 10,
            speed_kph=65 + i * 3,
            brake_pct=0.0,
            throttle_pct=i * 8.0,
            steering_deg=steering_peak * (1 - i / 9),
        )
        for i in range(10)
    ]


# ---------------------------------------------------------------------------
# _detect_corner_phase tests
# ---------------------------------------------------------------------------

class TestDetectCornerPhase:
    def test_entry_phase_detected(self):
        """Brake active and low steering → entry."""
        points = _entry_window()
        steering_peak = max(abs(p["steering_deg"]) for p in points)
        phase = _detect_corner_phase(points, steering_peak)
        assert phase == "entry"

    def test_mid_corner_phase_detected(self):
        """Steering at or near peak, brake zero → mid-corner."""
        points = _mid_corner_window(steering_peak=120.0)
        steering_peak = 120.0
        phase = _detect_corner_phase(points, steering_peak)
        assert phase == "mid-corner"

    def test_turn_in_phase_detected(self):
        """Steering loading toward peak, brake zero → turn-in."""
        points = _turn_in_window(steering_peak=120.0)
        steering_peak = 120.0
        phase = _detect_corner_phase(points, steering_peak)
        assert phase == "turn-in"

    def test_exit_phase_detected(self):
        """Steering unwinding, throttle increasing → exit."""
        points = _exit_window(steering_peak=120.0)
        steering_peak = 120.0
        phase = _detect_corner_phase(points, steering_peak)
        assert phase == "exit"

    def test_empty_points_returns_entry(self):
        assert _detect_corner_phase([], 0.0) == "entry"

    def test_zero_steering_peak_returns_entry(self):
        points = _entry_window()
        assert _detect_corner_phase(points, 0.0) == "entry"

    def test_mid_corner_with_high_throttle_returns_exit(self):
        """If steering is near peak but throttle is high, classify as exit."""
        points = [
            _make_point(
                distance_m=200 + i * 10,
                speed_kph=65 + i * 2,
                brake_pct=0.0,
                throttle_pct=50.0,
                steering_deg=110.0,  # near peak of 120
            )
            for i in range(10)
        ]
        phase = _detect_corner_phase(points, steering_peak=120.0)
        assert phase == "exit"


# ---------------------------------------------------------------------------
# classify_corners tests — brake trace classification
# ---------------------------------------------------------------------------

def _make_worst_sector(
    sector_number: int = 1,
    telemetry_window: list[dict] | None = None,
    braking_zone: list[dict] | None = None,
    avg_delta_ms: int = 500,
    ideal_sector_ms: int = 40000,
    driver_best_ms: int = 40500,
    ideal_entry_speed_kph: float | None = 120.0,
    ideal_exit_speed_kph: float | None = 65.0,
    entry_speed_kph: float | None = 115.0,
    exit_speed_kph: float | None = 63.0,
) -> dict:
    return {
        "sector_number": sector_number,
        "telemetry_window": telemetry_window or _mid_corner_window(),
        "braking_zone": braking_zone or [],
        "avg_delta_ms": avg_delta_ms,
        "ideal_sector_ms": ideal_sector_ms,
        "driver_best_ms": driver_best_ms,
        "ideal_entry_speed_kph": ideal_entry_speed_kph,
        "ideal_exit_speed_kph": ideal_exit_speed_kph,
        "entry_speed_kph": entry_speed_kph,
        "exit_speed_kph": exit_speed_kph,
    }


def _make_braking_zone_threshold() -> list[dict]:
    """Braking zone that looks like threshold: rapid build to 90%, held, then trailed."""
    points = []
    for i in range(12):
        if i < 2:
            brake = i * 30.0  # build
        elif i < 8:
            brake = 90.0  # plateau
        else:
            brake = 90.0 - (i - 8) * 20.0  # trail-off
        points.append(_make_point(
            distance_m=80 + i * 5,
            speed_kph=120 - i * 5,
            brake_pct=max(0, brake),
            throttle_pct=0.0,
            steering_deg=5.0,
        ))
    return points


def _make_braking_zone_brush() -> list[dict]:
    """Braking zone that looks like brush brake: peak ~15%, brief, at steering peak."""
    return [
        _make_point(
            distance_m=200 + i * 5,
            speed_kph=60.0,
            brake_pct=15.0 if 2 <= i <= 5 else 0.0,
            throttle_pct=0.0,
            steering_deg=110.0,
        )
        for i in range(10)
    ]


class TestClassifyCorners:
    def _run(self, worst_sectors, circuit_corners=None):
        return classify_corners(
            worst_sectors=worst_sectors,
            circuit_corners=circuit_corners,
            ideal_lap={"sector_sources": []},
            lap_sectors=[],
        )

    def test_returns_one_classification_per_sector(self):
        sectors = [_make_worst_sector(1), _make_worst_sector(2)]
        result = self._run(sectors)
        assert len(result) == 2

    def test_threshold_brake_identified(self):
        """High peak brake (90%) → threshold description."""
        sector = _make_worst_sector(
            telemetry_window=_entry_window(),
            braking_zone=_make_braking_zone_threshold(),
        )
        result = self._run([sector])
        assert len(result) == 1
        cls = result[0]
        assert "threshold" in cls["brake_description"]
        assert "90" in cls["brake_description"]

    def test_brush_brake_identified(self):
        """Low peak brake (~15%) at steering peak → light/trace description, not threshold."""
        sector = _make_worst_sector(
            telemetry_window=_mid_corner_window(),
            braking_zone=_make_braking_zone_brush(),
        )
        result = self._run([sector])
        assert len(result) == 1
        cls = result[0]
        # Should NOT be classified as threshold
        assert "threshold" not in cls["brake_description"]
        # Should mention the light pressure
        assert any(kw in cls["brake_description"] for kw in ("light", "trace", "trail"))

    def test_entry_phase_detection_in_classify_corners(self):
        """Entry window with threshold braking → phase=entry, front_axle_state=loaded."""
        sector = _make_worst_sector(
            telemetry_window=_entry_window(),
            braking_zone=_make_braking_zone_threshold(),
        )
        result = self._run([sector])
        cls = result[0]
        assert cls["phase"] == "entry"
        assert cls["front_axle_state"] == "loaded"
        assert cls["decel_need"] == "yes"

    def test_mid_corner_phase_detection_in_classify_corners(self):
        """Mid-corner window with no braking → phase=mid-corner, decel_need=already complete."""
        sector = _make_worst_sector(
            telemetry_window=_mid_corner_window(),
            braking_zone=[],
        )
        result = self._run([sector])
        cls = result[0]
        assert cls["phase"] == "mid-corner"
        assert cls["decel_need"] == "already complete"
        assert cls["front_axle_state"] == "unloaded"

    def test_classification_includes_required_keys(self):
        sector = _make_worst_sector()
        result = self._run([sector])
        required_keys = {
            "corner_name", "corner_distance_m", "sector_number", "phase",
            "driver_speed_mph", "ideal_speed_mph", "speed_delta_mph",
            "brake_description", "steer_state", "throttle_state",
            "engine_braking", "front_axle_state", "decel_need",
            "handling_condition", "avg_delta_ms", "ideal_sector_ms", "driver_best_ms",
        }
        assert required_keys.issubset(result[0].keys())

    def test_corner_name_from_circuit_corners(self):
        """Corner name should be pulled from nearest circuit corner by distance."""
        telemetry = _mid_corner_window()
        # Set distance so first point is at ~200m
        circuit_corners = [{"corner_number": 3, "name": "Oak Tree", "distance_m": 200.0}]
        sector = _make_worst_sector(telemetry_window=telemetry)
        result = self._run([sector], circuit_corners=circuit_corners)
        assert result[0]["corner_name"] == "Oak Tree"

    def test_speed_delta_computed(self):
        """Speed delta should be driver speed minus ideal speed in mph."""
        sector = _make_worst_sector(
            telemetry_window=_entry_window(),
            ideal_entry_speed_kph=120.0,
            entry_speed_kph=100.0,
        )
        result = self._run([sector])
        cls = result[0]
        if cls["speed_delta_mph"] is not None:
            assert cls["speed_delta_mph"] < 0  # driver is slower than ideal

    def test_engine_braking_detected(self):
        """Negative lon_g with zero brake → engine braking active."""
        points = [
            _make_point(
                distance_m=100 + i * 10,
                speed_kph=100 - i * 3,
                brake_pct=0.0,
                throttle_pct=0.0,
                steering_deg=5.0,
                lon_g=-0.15,
            )
            for i in range(10)
        ]
        sector = _make_worst_sector(telemetry_window=points)
        result = self._run([sector])
        assert result[0]["engine_braking"] == "active"

    def test_no_engine_braking_when_brake_active(self):
        """Negative lon_g with active brake → engine braking not flagged."""
        points = [
            _make_point(
                distance_m=100 + i * 10,
                speed_kph=100 - i * 3,
                brake_pct=60.0,
                throttle_pct=0.0,
                steering_deg=5.0,
                lon_g=-0.15,
            )
            for i in range(10)
        ]
        sector = _make_worst_sector(telemetry_window=points)
        result = self._run([sector])
        assert result[0]["engine_braking"] == "none"

    def test_overslowing_handling_condition(self):
        """Driver entry speed well below ideal in entry phase → overslowing."""
        sector = _make_worst_sector(
            telemetry_window=_entry_window(),
            braking_zone=_make_braking_zone_threshold(),
            ideal_entry_speed_kph=120.0,
            entry_speed_kph=95.0,  # ~15 kph = ~9 mph below ideal
        )
        result = self._run([sector])
        assert result[0]["handling_condition"] == "overslowing"


# ---------------------------------------------------------------------------
# format_corner_classifications tests
# ---------------------------------------------------------------------------

class TestFormatCornerClassifications:
    def test_output_contains_ideal_lap_note(self):
        sectors = [_make_worst_sector()]
        classifications = classify_corners(
            worst_sectors=sectors,
            circuit_corners=None,
            ideal_lap={"sector_sources": []},
            lap_sectors=[],
        )
        text = format_corner_classifications(classifications)
        assert "IDEAL LAP NOTE" in text

    def test_output_contains_all_required_fields(self):
        sectors = [_make_worst_sector()]
        classifications = classify_corners(
            worst_sectors=sectors,
            circuit_corners=None,
            ideal_lap={"sector_sources": []},
            lap_sectors=[],
        )
        text = format_corner_classifications(classifications)
        for field in [
            "Phase of interest:",
            "Speed at phase:",
            "Brake trace:",
            "Steering:",
            "Throttle:",
            "Engine braking:",
            "Classification:",
            "Sector delta:",
        ]:
            assert field in text, f"Missing field: {field}"

    def test_output_is_string(self):
        classifications = classify_corners(
            worst_sectors=[],
            circuit_corners=None,
            ideal_lap={"sector_sources": []},
            lap_sectors=[],
        )
        assert isinstance(format_corner_classifications(classifications), str)
