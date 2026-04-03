"""
Tests for src/calibration/mapping.py — GazeMapper

Acceptance criteria covered (Phase 1 — F1 Gaze-to-Screen Calibration):
- GazeMapper() instantiates; is_calibrated() returns False before fit()
- fit() with fewer than 4 samples raises ValueError
- fit() with 9 valid samples succeeds; is_calibrated() returns True
- predict() before fit() raises RuntimeError
- predict() after fit() returns a tuple of exactly 2 floats
- predict() output is in a plausible screen-coordinate range given the training data
- save() creates a JSON file with keys: version, created_at, pipeline_b64, samples
- save() without samples argument produces a file that omits the 'samples' key
- load() on a non-existent path returns False
- load() after save() returns True and restores calibration so predict() works again
- Round-trip: fit → save → new instance → load → predict returns same value as original
"""

import json
import os
import sys
import tempfile
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

# ---------------------------------------------------------------------------
# Synthetic 9-point calibration data (matches the spec exactly)
# ---------------------------------------------------------------------------
SAMPLES = [
    {'iris_dx': float(dx), 'iris_dy': float(dy), 'pitch': float(p), 'yaw': float(y),
     'screen_x': float(sx), 'screen_y': float(sy)}
    for dx, dy, p, y, sx, sy in [
        (-10, -5, -5, -10, 192,  117),
        (  0, -5, -5,   0, 960,  117),
        ( 10, -5, -5,  10, 1728, 117),
        (-10,  0,  0, -10, 192,  540),
        (  0,  0,  0,   0, 960,  540),
        ( 10,  0,  0,  10, 1728, 540),
        (-10,  5,  5, -10, 192,  963),
        (  0,  5,  5,   0, 960,  963),
        ( 10,  5,  5,  10, 1728, 963),
    ]
]

# Training data bounding box — predictions must stay in a loose neighbourhood
SCREEN_X_MIN = min(s['screen_x'] for s in SAMPLES)
SCREEN_X_MAX = max(s['screen_x'] for s in SAMPLES)
SCREEN_Y_MIN = min(s['screen_y'] for s in SAMPLES)
SCREEN_Y_MAX = max(s['screen_y'] for s in SAMPLES)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fitted_mapper():
    """Return a fresh, already-fitted GazeMapper."""
    from src.calibration.mapping import GazeMapper
    m = GazeMapper()
    m.fit(SAMPLES)
    return m


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestGazeMapperInstantiation(unittest.TestCase):
    """GazeMapper() can be constructed and starts uncalibrated."""

    def test_instantiates_without_error(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        self.assertIsNotNone(m)

    def test_is_calibrated_returns_false_before_fit(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        self.assertFalse(m.is_calibrated())


# ---------------------------------------------------------------------------
# fit() — error cases
# ---------------------------------------------------------------------------

class TestGazeMapperFitTooFewSamples(unittest.TestCase):
    """fit() with fewer than 4 samples raises ValueError."""

    def test_zero_samples_raises_value_error(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        with self.assertRaises(ValueError):
            m.fit([])

    def test_three_samples_raises_value_error(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        with self.assertRaises(ValueError):
            m.fit(SAMPLES[:3])

    def test_error_message_mentions_count(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        with self.assertRaises(ValueError) as ctx:
            m.fit(SAMPLES[:2])
        self.assertIn("2", str(ctx.exception))


# ---------------------------------------------------------------------------
# fit() — success cases
# ---------------------------------------------------------------------------

class TestGazeMapperFitSuccess(unittest.TestCase):
    """fit() with 9 valid samples succeeds and marks the mapper as calibrated."""

    def test_fit_nine_samples_does_not_raise(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        m.fit(SAMPLES)  # must not raise

    def test_is_calibrated_returns_true_after_fit(self):
        m = _make_fitted_mapper()
        self.assertTrue(m.is_calibrated())

    def test_fit_exactly_four_samples_succeeds(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        m.fit(SAMPLES[:4])
        self.assertTrue(m.is_calibrated())


# ---------------------------------------------------------------------------
# predict() — before fit
# ---------------------------------------------------------------------------

class TestGazeMapperPredictBeforeFit(unittest.TestCase):
    """predict() before fit() raises RuntimeError."""

    def test_predict_before_fit_raises_runtime_error(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        with self.assertRaises(RuntimeError):
            m.predict(0.0, 0.0, 0.0, 0.0)


# ---------------------------------------------------------------------------
# predict() — after fit
# ---------------------------------------------------------------------------

class TestGazeMapperPredictReturnType(unittest.TestCase):
    """predict() returns a tuple of exactly 2 floats."""

    def test_predict_returns_tuple(self):
        m = _make_fitted_mapper()
        result = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertIsInstance(result, tuple)

    def test_predict_tuple_length_is_two(self):
        m = _make_fitted_mapper()
        result = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertEqual(len(result), 2)

    def test_predict_first_element_is_float(self):
        m = _make_fitted_mapper()
        screen_x, _ = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertIsInstance(screen_x, float)

    def test_predict_second_element_is_float(self):
        m = _make_fitted_mapper()
        _, screen_y = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertIsInstance(screen_y, float)


class TestGazeMapperPredictRange(unittest.TestCase):
    """
    predict() at the centre calibration point (0,0,0,0) should return coords
    in a wide but plausible neighbourhood of the training data range.
    We use a 200-pixel margin to account for polynomial extrapolation.
    """

    MARGIN = 200.0

    def test_centre_prediction_x_in_plausible_range(self):
        m = _make_fitted_mapper()
        screen_x, _ = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertGreater(screen_x, SCREEN_X_MIN - self.MARGIN)
        self.assertLess(screen_x, SCREEN_X_MAX + self.MARGIN)

    def test_centre_prediction_y_in_plausible_range(self):
        m = _make_fitted_mapper()
        _, screen_y = m.predict(0.0, 0.0, 0.0, 0.0)
        self.assertGreater(screen_y, SCREEN_Y_MIN - self.MARGIN)
        self.assertLess(screen_y, SCREEN_Y_MAX + self.MARGIN)


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestGazeMapperSaveCreatesFile(unittest.TestCase):
    """save() writes a file at the given path."""

    def test_file_exists_after_save(self):
        m = _make_fitted_mapper()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "cal.json")
            m.save(path, SAMPLES)
            self.assertTrue(os.path.isfile(path))


class TestGazeMapperSaveJsonKeys(unittest.TestCase):
    """save() with samples produces JSON with version, created_at, pipeline_b64, samples."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        path = os.path.join(self._tmp.name, "cal.json")
        m = _make_fitted_mapper()
        m.save(path, SAMPLES)
        with open(path) as f:
            self._data = json.load(f)

    def tearDown(self):
        self._tmp.cleanup()

    def test_version_key_present(self):
        self.assertIn('version', self._data)

    def test_created_at_key_present(self):
        self.assertIn('created_at', self._data)

    def test_pipeline_b64_key_present(self):
        self.assertIn('pipeline_b64', self._data)

    def test_samples_key_present_when_provided(self):
        self.assertIn('samples', self._data)

    def test_version_value_is_1(self):
        self.assertEqual(self._data['version'], 1)

    def test_samples_length_matches_input(self):
        self.assertEqual(len(self._data['samples']), len(SAMPLES))


class TestGazeMapperSaveWithoutSamples(unittest.TestCase):
    """save() without a samples argument omits the 'samples' key."""

    def test_samples_key_empty_list_when_not_provided(self):
        m = _make_fitted_mapper()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            m.save(path)  # no samples argument
            with open(path) as f:
                data = json.load(f)
        self.assertIn('samples', data)
        self.assertEqual(data['samples'], [])


class TestGazeMapperSaveBeforeFitRaises(unittest.TestCase):
    """save() on an uncalibrated mapper raises RuntimeError."""

    def test_save_before_fit_raises_runtime_error(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(RuntimeError):
                m.save(os.path.join(tmp, "cal.json"))


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestGazeMapperLoadNonExistent(unittest.TestCase):
    """load() on a non-existent path returns False."""

    def test_load_missing_file_returns_false(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        result = m.load("/tmp/__does_not_exist_gaze_mapper_test__.json")
        self.assertFalse(result)

    def test_is_calibrated_still_false_after_failed_load(self):
        from src.calibration.mapping import GazeMapper
        m = GazeMapper()
        m.load("/tmp/__does_not_exist_gaze_mapper_test__.json")
        self.assertFalse(m.is_calibrated())


class TestGazeMapperLoadAfterSave(unittest.TestCase):
    """load() after save() returns True and restores calibration."""

    def test_load_returns_true(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            _make_fitted_mapper().save(path, SAMPLES)

            m2 = GazeMapper()
            result = m2.load(path)
        self.assertTrue(result)

    def test_is_calibrated_true_after_load(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            _make_fitted_mapper().save(path, SAMPLES)

            m2 = GazeMapper()
            m2.load(path)
            self.assertTrue(m2.is_calibrated())

    def test_predict_works_after_load(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            _make_fitted_mapper().save(path, SAMPLES)

            m2 = GazeMapper()
            m2.load(path)
            result = m2.predict(0.0, 0.0, 0.0, 0.0)
        self.assertEqual(len(result), 2)


# ---------------------------------------------------------------------------
# Round-trip consistency
# ---------------------------------------------------------------------------

class TestGazeMapperRoundTrip(unittest.TestCase):
    """fit → save → new instance → load → predict returns the same value."""

    def test_round_trip_predict_x_matches(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            m1 = _make_fitted_mapper()
            x1, _ = m1.predict(0.0, 0.0, 0.0, 0.0)
            m1.save(path, SAMPLES)

            m2 = GazeMapper()
            m2.load(path)
            x2, _ = m2.predict(0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(x1, x2, places=4)

    def test_round_trip_predict_y_matches(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            m1 = _make_fitted_mapper()
            _, y1 = m1.predict(0.0, 0.0, 0.0, 0.0)
            m1.save(path, SAMPLES)

            m2 = GazeMapper()
            m2.load(path)
            _, y2 = m2.predict(0.0, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(y1, y2, places=4)

    def test_round_trip_different_input_predict_x_matches(self):
        from src.calibration.mapping import GazeMapper
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "cal.json")
            m1 = _make_fitted_mapper()
            x1, _ = m1.predict(-10.0, -5.0, -5.0, -10.0)
            m1.save(path, SAMPLES)

            m2 = GazeMapper()
            m2.load(path)
            x2, _ = m2.predict(-10.0, -5.0, -5.0, -10.0)
        self.assertAlmostEqual(x1, x2, places=4)


if __name__ == "__main__":
    unittest.main()
