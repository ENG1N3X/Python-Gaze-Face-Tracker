"""
Tests for cursor accuracy MVP:
  - src/tracking/iris_filter.py — IrisFilter
  - src/control/snap_zones.py  — SnapZoneRegistry
  - src/control/cursor.py      — CursorController dual-speed EMA + snap
"""

import os
import sys
import unittest
from unittest.mock import patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _cursor_config(**overrides):
    base = {
        "smoothing_alpha": 0.08,
        "cursor_alpha_fast": 0.5,
        "cursor_fast_velocity_threshold_px": 50,
        "cursor_deadzone_px": 5,
        "snap_zones": [],
    }
    base.update(overrides)
    return base


def _make_cursor(config=None):
    from src.control.cursor import CursorController
    return CursorController(config or _cursor_config())


# ---------------------------------------------------------------------------
# IrisFilter
# ---------------------------------------------------------------------------

class TestIrisFilterNormal(unittest.TestCase):
    def test_returns_median_after_warm_up(self):
        from src.tracking.iris_filter import IrisFilter
        f = IrisFilter({"iris_filter_window": 5, "iris_spike_threshold_px": 8.0})
        for _ in range(5):
            dx, dy = f.update(10.0, 20.0)
        self.assertAlmostEqual(dx, 10.0, places=1)
        self.assertAlmostEqual(dy, 20.0, places=1)

    def test_cold_start_returns_raw_value(self):
        from src.tracking.iris_filter import IrisFilter
        f = IrisFilter({"iris_filter_window": 5, "iris_spike_threshold_px": 8.0})
        dx, dy = f.update(7.0, 3.0)
        self.assertAlmostEqual(dx, 7.0, places=1)
        self.assertAlmostEqual(dy, 3.0, places=1)


class TestIrisFilterSpikeRejection(unittest.TestCase):
    def test_spike_replaced_by_median(self):
        from src.tracking.iris_filter import IrisFilter
        f = IrisFilter({"iris_filter_window": 5, "iris_spike_threshold_px": 8.0})
        # Fill buffer with stable values
        for _ in range(5):
            f.update(10.0, 10.0)
        # Inject a spike far beyond threshold
        dx, dy = f.update(100.0, 100.0)
        self.assertLess(abs(dx - 10.0), 2.0, "spike dx should be suppressed")
        self.assertLess(abs(dy - 10.0), 2.0, "spike dy should be suppressed")

    def test_non_spike_passes_through(self):
        from src.tracking.iris_filter import IrisFilter
        f = IrisFilter({"iris_filter_window": 5, "iris_spike_threshold_px": 8.0})
        for _ in range(5):
            f.update(10.0, 10.0)
        # Small change — not a spike
        dx, dy = f.update(12.0, 11.0)
        # Median of [10,10,10,10,12] = 10; 12-10=2 < 8 so not spike; median shifts
        self.assertLess(abs(dx - 10.0), 3.0)


class TestIrisFilterReset(unittest.TestCase):
    def test_reset_clears_buffer(self):
        from src.tracking.iris_filter import IrisFilter
        f = IrisFilter({"iris_filter_window": 5, "iris_spike_threshold_px": 8.0})
        for _ in range(5):
            f.update(99.0, 99.0)
        f.reset()
        # After reset first value is raw
        dx, dy = f.update(5.0, 5.0)
        self.assertAlmostEqual(dx, 5.0, places=1)
        self.assertAlmostEqual(dy, 5.0, places=1)


# ---------------------------------------------------------------------------
# SnapZoneRegistry
# ---------------------------------------------------------------------------

class TestSnapZoneInsideZone(unittest.TestCase):
    def test_point_inside_zone_returns_center(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry([{"cx": 100, "cy": 200, "hw": 20, "hh": 20}])
        result = reg.snap(110, 210)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result[0], 100.0)
        self.assertAlmostEqual(result[1], 200.0)

    def test_point_on_boundary_is_inside(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry([{"cx": 100, "cy": 200, "hw": 20, "hh": 20}])
        # Exactly at boundary
        result = reg.snap(120, 220)
        self.assertIsNotNone(result)


class TestSnapZoneOutsideZone(unittest.TestCase):
    def test_point_outside_zone_returns_none(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry([{"cx": 100, "cy": 200, "hw": 20, "hh": 20}])
        result = reg.snap(200, 200)
        self.assertIsNone(result)

    def test_empty_zone_list_returns_none(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry([])
        self.assertIsNone(reg.snap(100, 100))


class TestSnapZoneMultiple(unittest.TestCase):
    def test_first_matching_zone_wins(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry([
            {"cx": 50,  "cy": 50,  "hw": 30, "hh": 30},
            {"cx": 60,  "cy": 60,  "hw": 30, "hh": 30},
        ])
        # (65, 65) is inside both zones; first should win
        result = reg.snap(65, 65)
        self.assertAlmostEqual(result[0], 50.0)
        self.assertAlmostEqual(result[1], 50.0)


class TestSnapZoneFromConfig(unittest.TestCase):
    def test_from_config_empty_list(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry.from_config({"snap_zones": []})
        self.assertIsNone(reg.snap(100, 100))

    def test_from_config_with_zone(self):
        from src.control.snap_zones import SnapZoneRegistry
        reg = SnapZoneRegistry.from_config({
            "snap_zones": [{"cx": 100, "cy": 100, "hw": 20, "hh": 20}]
        })
        result = reg.snap(105, 105)
        self.assertIsNotNone(result)


# ---------------------------------------------------------------------------
# CursorController — dual-speed EMA + snap
# ---------------------------------------------------------------------------

class TestCursorEMA(unittest.TestCase):
    def setUp(self):
        self.size_patch = patch("pyautogui.size", return_value=(1280, 800))
        self.move_patch = patch("pyautogui.moveTo")
        self.size_patch.start()
        self.mock_move = self.move_patch.start()

    def tearDown(self):
        self.size_patch.stop()
        self.move_patch.stop()

    def test_first_move_initializes_ema(self):
        c = _make_cursor()
        pos = c.move(100, 100)
        self.assertIsNotNone(pos)

    def test_slow_alpha_used_for_small_velocity(self):
        """Small movement → slow alpha → cursor stays closer to old position."""
        cfg = _cursor_config(
            smoothing_alpha=0.1,
            cursor_alpha_fast=0.9,
            cursor_fast_velocity_threshold_px=100,
        )
        c = _make_cursor(cfg)
        c.move(500, 400)  # init EMA at (500, 400)
        # Small step — velocity < 100
        pos = c.move(510, 410)
        # With slow alpha 0.1: new EMA ≈ 0.1*510 + 0.9*500 = 501
        self.assertLess(pos[0], 510)

    def test_fast_alpha_used_for_large_velocity(self):
        """Large saccade → fast alpha → cursor jumps closer to target."""
        cfg = _cursor_config(
            smoothing_alpha=0.1,
            cursor_alpha_fast=0.8,
            cursor_fast_velocity_threshold_px=50,
        )
        c = _make_cursor(cfg)
        c.move(100, 100)  # init EMA at (100, 100)
        # Large jump — velocity >> 50
        pos = c.move(900, 600)
        # With fast alpha 0.8: EMA ≈ 0.8*900 + 0.2*100 = 740
        self.assertGreater(pos[0], 400)

    def test_deadzone_prevents_small_moves(self):
        cfg = _cursor_config(cursor_deadzone_px=10)
        c = _make_cursor(cfg)
        c.move(500, 400)
        pos1 = c.move(500, 400)
        # Move by less than deadzone
        pos2 = c.move(503, 402)
        self.assertEqual(pos1, pos2)

    def test_reset_buffer_clears_ema(self):
        c = _make_cursor()
        c.move(500, 400)
        c.reset_buffer()
        # After reset, first move re-initialises EMA without history
        pos = c.move(200, 200)
        self.assertIsNotNone(pos)
        # EMA should be near 200 not 500
        self.assertLess(abs(pos[0] - 200), 50)


class TestCursorSnapZone(unittest.TestCase):
    def setUp(self):
        self.size_patch = patch("pyautogui.size", return_value=(1280, 800))
        self.move_patch = patch("pyautogui.moveTo")
        self.size_patch.start()
        self.mock_move = self.move_patch.start()

    def tearDown(self):
        self.size_patch.stop()
        self.move_patch.stop()

    def test_ac4_snap_zone_at_100_100(self):
        """AC4: zone at (100,100) hw=20 hh=20, input (112,108) → output (100,100)."""
        cfg = _cursor_config(
            smoothing_alpha=1.0,       # alpha=1 so EMA = raw input immediately
            cursor_alpha_fast=1.0,
            cursor_fast_velocity_threshold_px=0,
            cursor_deadzone_px=0,
            snap_zones=[{"cx": 100, "cy": 100, "hw": 20, "hh": 20}],
        )
        c = _make_cursor(cfg)
        pos = c.move(112, 108)
        self.assertEqual(pos, (100, 100))

    def test_ac5_outside_zone_no_snap(self):
        """AC5: zone at (100,100), input (200,200) → no snap, raw EMA returned."""
        cfg = _cursor_config(
            smoothing_alpha=1.0,
            cursor_alpha_fast=1.0,
            cursor_fast_velocity_threshold_px=0,
            cursor_deadzone_px=0,
            snap_zones=[{"cx": 100, "cy": 100, "hw": 20, "hh": 20}],
        )
        c = _make_cursor(cfg)
        pos = c.move(200, 200)
        self.assertNotEqual(pos, (100, 100))
        self.assertAlmostEqual(pos[0], 200, delta=2)
        self.assertAlmostEqual(pos[1], 200, delta=2)


if __name__ == "__main__":
    unittest.main()
