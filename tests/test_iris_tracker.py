"""
Tests for src/tracking/iris_tracker.py

Acceptance criteria covered:
- get_iris_positions returns a dict with all expected keys
- l_dx, l_dy are integers
- l_center is a numpy array of shape (2,)
- All index constants (LEFT_IRIS, RIGHT_IRIS, etc.) are non-empty lists

The cv2 dependency (minEnclosingCircle) is exercised with a synthetic mesh_points
array — no camera or MediaPipe hardware needed.
"""

import os
import sys
import unittest

import numpy as np

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def _make_mesh_points(num_landmarks: int = 478) -> np.ndarray:
    """
    Build a synthetic (num_landmarks, 2) int32 array.
    All points sit at integer pixel positions derived from their index so that
    no two iris points are coincident (minEnclosingCircle needs at least 1 non-
    degenerate point).
    """
    pts = np.zeros((num_landmarks, 2), dtype=np.int32)
    for i in range(num_landmarks):
        pts[i] = [100 + (i % 50), 100 + (i // 50)]
    return pts


# ── Constants ─────────────────────────────────────────────────────────────────

class TestIndexConstantsExist(unittest.TestCase):
    def test_LEFT_IRIS_is_list(self):
        from src.tracking.iris_tracker import LEFT_IRIS
        self.assertIsInstance(LEFT_IRIS, list)

    def test_LEFT_IRIS_is_non_empty(self):
        from src.tracking.iris_tracker import LEFT_IRIS
        self.assertGreater(len(LEFT_IRIS), 0)

    def test_RIGHT_IRIS_is_list(self):
        from src.tracking.iris_tracker import RIGHT_IRIS
        self.assertIsInstance(RIGHT_IRIS, list)

    def test_RIGHT_IRIS_is_non_empty(self):
        from src.tracking.iris_tracker import RIGHT_IRIS
        self.assertGreater(len(RIGHT_IRIS), 0)

    def test_LEFT_EYE_OUTER_CORNER_is_non_empty(self):
        from src.tracking.iris_tracker import LEFT_EYE_OUTER_CORNER
        self.assertGreater(len(LEFT_EYE_OUTER_CORNER), 0)

    def test_LEFT_EYE_INNER_CORNER_is_non_empty(self):
        from src.tracking.iris_tracker import LEFT_EYE_INNER_CORNER
        self.assertGreater(len(LEFT_EYE_INNER_CORNER), 0)

    def test_RIGHT_EYE_OUTER_CORNER_is_non_empty(self):
        from src.tracking.iris_tracker import RIGHT_EYE_OUTER_CORNER
        self.assertGreater(len(RIGHT_EYE_OUTER_CORNER), 0)

    def test_RIGHT_EYE_INNER_CORNER_is_non_empty(self):
        from src.tracking.iris_tracker import RIGHT_EYE_INNER_CORNER
        self.assertGreater(len(RIGHT_EYE_INNER_CORNER), 0)

    def test_RIGHT_EYE_POINTS_is_non_empty(self):
        from src.tracking.iris_tracker import RIGHT_EYE_POINTS
        self.assertGreater(len(RIGHT_EYE_POINTS), 0)

    def test_LEFT_EYE_POINTS_is_non_empty(self):
        from src.tracking.iris_tracker import LEFT_EYE_POINTS
        self.assertGreater(len(LEFT_EYE_POINTS), 0)


# ── get_iris_positions return structure ───────────────────────────────────────

class TestGetIrisPositionsReturnType(unittest.TestCase):
    def test_returns_dict(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result, dict)


class TestGetIrisPositionsAllKeys(unittest.TestCase):
    EXPECTED_KEYS = {
        "l_center", "r_center",
        "l_cx", "l_cy",
        "r_cx", "r_cy",
        "l_dx", "l_dy",
        "r_dx", "r_dy",
        "l_radius", "r_radius",
    }

    def test_all_expected_keys_present(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        for key in self.EXPECTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, result)


class TestGetIrisPositionsDxDyAreNumeric(unittest.TestCase):
    """l_dx and l_dy must be numeric (int or float) — iris coords are now float32."""

    def test_l_dx_is_numeric(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["l_dx"], (int, float, np.number))

    def test_l_dy_is_numeric(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["l_dy"], (int, float, np.number))

    def test_r_dx_is_numeric(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["r_dx"], (int, float, np.number))

    def test_r_dy_is_numeric(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["r_dy"], (int, float, np.number))


class TestGetIrisPositionsLCenterShape(unittest.TestCase):
    """l_center must be a numpy array of shape (2,)."""

    def test_l_center_is_ndarray(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["l_center"], np.ndarray)

    def test_l_center_shape_is_2(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertEqual(result["l_center"].shape, (2,))

    def test_r_center_is_ndarray(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertIsInstance(result["r_center"], np.ndarray)

    def test_r_center_shape_is_2(self):
        from src.tracking.iris_tracker import get_iris_positions
        result = get_iris_positions(_make_mesh_points())
        self.assertEqual(result["r_center"].shape, (2,))


class TestGetIrisPositionsDxDySemantics(unittest.TestCase):
    """
    l_dx = l_center.x - LEFT_EYE_OUTER_CORNER.x
    Verify sign and magnitude make sense for a known synthetic layout.
    """

    def test_l_dx_matches_vector_definition(self):
        from src.tracking.iris_tracker import (
            LEFT_EYE_OUTER_CORNER,
            LEFT_IRIS,
            get_iris_positions,
        )
        import cv2

        mesh = _make_mesh_points()
        result = get_iris_positions(mesh)

        (l_cx, _), _ = cv2.minEnclosingCircle(mesh[LEFT_IRIS])
        outer_x = mesh[LEFT_EYE_OUTER_CORNER][0][0]
        expected_dx = float(l_cx) - float(outer_x)
        self.assertAlmostEqual(float(result["l_dx"]), expected_dx, places=3)


if __name__ == "__main__":
    unittest.main()
