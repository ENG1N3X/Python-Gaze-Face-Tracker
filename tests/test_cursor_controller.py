"""
Tests for src/control/cursor.py — CursorController

Phase 2 acceptance criteria covered (PRODUCT.md F2 — Cursor Control):
- AC1: move() calls pyautogui.moveTo() with integer coordinates (happy path)
- AC2: move() when disabled does NOT call pyautogui.moveTo()
- AC3: coords outside screen bounds are clamped before smoothing
- AC4: after the smoothing buffer fills with identical values the output equals
       those values (buffer converged)
- AC5: set_enabled(False) / set_enabled(True) flips is_enabled() correctly
- AC6: move() passes integers, not floats, to pyautogui.moveTo()
- AC7: clamping upper boundary — exactly at screen_w-1 / screen_h-1 is accepted
- AC8: clamping lower boundary — negative coords clamp to 0
- AC9: toggle sequence enabled→disabled→enabled restores movement
- AC10: re-enabling after disable resumes calling pyautogui.moveTo()

Mock strategy: patch 'src.control.cursor.pyautogui' so the module-level import
is replaced; also set FAILSAFE/PAUSE attributes on the mock to avoid AttributeError
during __init__.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, call

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Minimal config — only the key CursorController reads
CONFIG_5 = {"smoothing_window": 5}


def _make_controller(mock_pg, config=None):
    """Instantiate CursorController with the supplied pyautogui mock active."""
    from src.control.cursor import CursorController
    mock_pg.size.return_value = (1920, 1080)
    return CursorController(config or CONFIG_5)


# ---------------------------------------------------------------------------
# AC1 — Happy path: move() calls pyautogui.moveTo()
# ---------------------------------------------------------------------------

class TestCursorMoveCallsMoveTo(unittest.TestCase):
    """move() with valid coords reaches pyautogui.moveTo() at least once."""

    def test_move_calls_moveto(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.move(500.0, 400.0)
        mock_pg.moveTo.assert_called_once()


# ---------------------------------------------------------------------------
# AC6 — moveTo receives integer arguments (not floats)
# ---------------------------------------------------------------------------

class TestCursorMovePassesIntegers(unittest.TestCase):
    """pyautogui.moveTo() must receive int arguments, not float."""

    def test_moveto_first_arg_is_int(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.move(500.0, 400.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertIsInstance(args[0], int)

    def test_moveto_second_arg_is_int(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.move(500.0, 400.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertIsInstance(args[1], int)


# ---------------------------------------------------------------------------
# AC2 — Disabled: move() does NOT call moveTo()
# ---------------------------------------------------------------------------

class TestCursorMoveDisabled(unittest.TestCase):
    """move() when controller is disabled must not call pyautogui.moveTo()."""

    def test_disabled_move_does_not_call_moveto(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.set_enabled(False)
            ctrl.move(500.0, 400.0)
        mock_pg.moveTo.assert_not_called()

    def test_disabled_move_multiple_calls_still_silent(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.set_enabled(False)
            for _ in range(10):
                ctrl.move(100.0, 200.0)
        mock_pg.moveTo.assert_not_called()


# ---------------------------------------------------------------------------
# AC3 — Clamping: coords beyond screen bounds are clamped
# ---------------------------------------------------------------------------

class TestCursorClamping(unittest.TestCase):
    """Coordinates outside [0, screen_w-1] / [0, screen_h-1] are clamped."""

    # screen: 1920 x 1080  →  valid x: 0..1919, valid y: 0..1079

    def test_x_above_max_clamped_to_screen_w_minus_1(self):
        """x = 2000 (> 1919) must produce moveTo x <= 1919 after convergence."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(2000.0, 540.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertLessEqual(args[0], 1919)

    def test_y_above_max_clamped_to_screen_h_minus_1(self):
        """y = 2000 (> 1079) must produce moveTo y <= 1079 after convergence."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(960.0, 2000.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertLessEqual(args[1], 1079)

    def test_x_negative_clamped_to_zero(self):
        """x = -50 must produce moveTo x >= 0."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(-50.0, 540.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertGreaterEqual(args[0], 0)

    def test_y_negative_clamped_to_zero(self):
        """y = -1 must produce moveTo y >= 0."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(960.0, -1.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertGreaterEqual(args[1], 0)

    def test_x_at_exact_boundary_screen_w_minus_1_not_clamped(self):
        """x = 1919.0 is at the upper boundary; must not be clamped further."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(1919.0, 540.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertEqual(args[0], 1919)

    def test_x_at_screen_w_exact_clamped_to_screen_w_minus_1(self):
        """x = 1920 (== screen_w) is one beyond the boundary; must clamp to 1919."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 1})
            ctrl.move(1920.0, 540.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertEqual(args[0], 1919)


# ---------------------------------------------------------------------------
# AC4 — Smoothing: buffer convergence
# ---------------------------------------------------------------------------

class TestCursorSmoothing(unittest.TestCase):
    """After filling the buffer with the same coords, output equals those coords."""

    def test_buffer_converges_after_n_identical_moves(self):
        """Five identical moves with window=5 should produce (300, 200) exactly."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 5})
            for _ in range(5):
                ctrl.move(300.0, 200.0)
            args, _ = mock_pg.moveTo.call_args  # last call
        self.assertEqual(args[0], 300)
        self.assertEqual(args[1], 200)

    def test_buffer_converges_to_different_coords(self):
        """Window=3: three identical moves to (750, 600) converges correctly."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg, {"smoothing_window": 3})
            for _ in range(3):
                ctrl.move(750.0, 600.0)
            args, _ = mock_pg.moveTo.call_args
        self.assertEqual(args[0], 750)
        self.assertEqual(args[1], 600)


# ---------------------------------------------------------------------------
# AC5 — Toggle: set_enabled flips is_enabled
# ---------------------------------------------------------------------------

class TestCursorToggle(unittest.TestCase):
    """set_enabled() / is_enabled() contract."""

    def test_enabled_by_default(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
        self.assertTrue(ctrl.is_enabled())

    def test_set_enabled_false_makes_is_enabled_return_false(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.set_enabled(False)
        self.assertFalse(ctrl.is_enabled())

    def test_set_enabled_true_makes_is_enabled_return_true(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.set_enabled(False)
            ctrl.set_enabled(True)
        self.assertTrue(ctrl.is_enabled())

    def test_double_disable_leaves_disabled(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)
            ctrl.set_enabled(False)
            ctrl.set_enabled(False)
        self.assertFalse(ctrl.is_enabled())


# ---------------------------------------------------------------------------
# AC9 + AC10 — Toggle sequence: disable then re-enable resumes movement
# ---------------------------------------------------------------------------

class TestCursorToggleResumesMovement(unittest.TestCase):
    """Re-enabling after disable must resume calls to pyautogui.moveTo()."""

    def test_reenable_after_disable_calls_moveto(self):
        with patch("src.control.cursor.pyautogui") as mock_pg:
            ctrl = _make_controller(mock_pg)

            # Disabled — no call
            ctrl.set_enabled(False)
            ctrl.move(500.0, 400.0)
            mock_pg.moveTo.assert_not_called()

            # Re-enabled — call must happen
            ctrl.set_enabled(True)
            ctrl.move(500.0, 400.0)
        mock_pg.moveTo.assert_called_once()

    def test_move_call_count_reflects_enabled_state(self):
        """Two moves while enabled, two while disabled, two while re-enabled → 4 calls total."""
        with patch("src.control.cursor.pyautogui") as mock_pg:
            # deadzone=0 so every distinct position triggers moveTo
            from src.control.cursor import CursorController
            mock_pg.size.return_value = (1920, 1080)
            ctrl = CursorController({"smoothing_alpha": 1.0, "cursor_alpha_fast": 1.0,
                                     "cursor_fast_velocity_threshold_px": 0,
                                     "cursor_deadzone_px": 0, "snap_zones": []})

            ctrl.move(100.0, 100.0)
            ctrl.move(200.0, 200.0)

            ctrl.set_enabled(False)
            ctrl.move(300.0, 300.0)
            ctrl.move(400.0, 400.0)

            ctrl.set_enabled(True)
            ctrl.move(500.0, 500.0)
            ctrl.move(600.0, 600.0)

        self.assertEqual(mock_pg.moveTo.call_count, 4)


if __name__ == "__main__":
    unittest.main()
