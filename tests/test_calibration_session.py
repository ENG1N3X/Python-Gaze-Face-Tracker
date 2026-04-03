"""
Tests for src/calibration/calibration.py — CalibrationSession

Acceptance criteria covered (Phase 1 — F1 Gaze-to-Screen Calibration):
- CalibrationSession instantiates with a config dict
- save() writes a JSON file with a 'samples' key
- load() returns None for a non-existent path
- load() after save() returns the original samples list
- run() with mocked camera/tracker/head_pose/CalibrationUI:
    - returns a list of exactly 9 dicts
    - each dict has keys: iris_dx, iris_dy, pitch, yaw, screen_x, screen_y
    - iris_dx value is the average of the mocked l_dx and r_dx values
    - screen_x values correspond to the expected 3x3 grid column positions
    - screen_y values correspond to the expected 3x3 grid row positions
"""

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch, call

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import numpy as np

# ---------------------------------------------------------------------------
# Minimal config — must satisfy all keys CalibrationSession reads
# ---------------------------------------------------------------------------
MINIMAL_CONFIG = {
    "calibration_dwell_sec": 1.0,
    "calibration_points": 9,
    "calibration_collect_frames": 3,   # small value so tests run quickly
}

# Synthetic samples list (caller is responsible for these — CalibrationSession
# just stores/loads them)
SYNTHETIC_SAMPLES = [
    {'iris_dx': float(dx), 'iris_dy': float(dy),
     'pitch': float(p), 'yaw': float(y),
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_session():
    from src.calibration.calibration import CalibrationSession
    return CalibrationSession(MINIMAL_CONFIG)


def _mock_iris_return():
    """Return value for get_iris_positions mock (per the spec)."""
    return {
        'l_dx': 5, 'l_dy': 2,
        'r_dx': 5, 'r_dy': 2,
        'l_cx': 100, 'l_cy': 100,
        'r_cx': 200, 'r_cy': 100,
        'l_center': np.array([100, 100]),
        'r_center': np.array([200, 100]),
        'l_radius': 10.0,
        'r_radius': 10.0,
    }


def _build_mock_mesh():
    """Produce mesh_points (478,2) and mesh_points_3d (478,3) all zeros."""
    mesh_points = np.zeros((478, 2), dtype=np.int32)
    mesh_points_3d = np.zeros((478, 3), dtype=np.float32)
    return mesh_points, mesh_points_3d


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

class TestCalibrationSessionInstantiation(unittest.TestCase):
    """CalibrationSession can be constructed with a valid config dict."""

    def test_instantiates_without_error(self):
        session = _make_session()
        self.assertIsNotNone(session)


# ---------------------------------------------------------------------------
# save()
# ---------------------------------------------------------------------------

class TestCalibrationSessionSave(unittest.TestCase):
    """save() writes a valid JSON file with a 'samples' key."""

    def test_file_is_created_after_save(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "sub", "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            self.assertTrue(os.path.isfile(path))

    def test_saved_file_contains_samples_key(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            with open(path) as f:
                data = json.load(f)
        self.assertIn('samples', data)

    def test_saved_samples_count_matches_input(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            with open(path) as f:
                data = json.load(f)
        self.assertEqual(len(data['samples']), len(SYNTHETIC_SAMPLES))

    def test_saved_file_contains_version_key(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            with open(path) as f:
                data = json.load(f)
        self.assertIn('version', data)

    def test_saved_file_contains_created_at_key(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            with open(path) as f:
                data = json.load(f)
        self.assertIn('created_at', data)


# ---------------------------------------------------------------------------
# load()
# ---------------------------------------------------------------------------

class TestCalibrationSessionLoadMissing(unittest.TestCase):
    """load() returns None when the file does not exist."""

    def test_load_missing_file_returns_none(self):
        session = _make_session()
        result = session.load("/tmp/__does_not_exist_calibration_session__.json")
        self.assertIsNone(result)


class TestCalibrationSessionLoadAfterSave(unittest.TestCase):
    """load() after save() returns the original samples list."""

    def test_load_returns_list(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            result = session.load(path)
        self.assertIsInstance(result, list)

    def test_load_returns_same_count(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            result = session.load(path)
        self.assertEqual(len(result), len(SYNTHETIC_SAMPLES))

    def test_load_preserves_iris_dx(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            result = session.load(path)
        self.assertAlmostEqual(result[0]['iris_dx'], SYNTHETIC_SAMPLES[0]['iris_dx'])

    def test_load_preserves_screen_x(self):
        session = _make_session()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            result = session.load(path)
        self.assertAlmostEqual(result[4]['screen_x'], SYNTHETIC_SAMPLES[4]['screen_x'])

    def test_load_preserves_all_sample_keys(self):
        session = _make_session()
        expected_keys = {'iris_dx', 'iris_dy', 'pitch', 'yaw', 'screen_x', 'screen_y'}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "calibration.json")
            session.save(SYNTHETIC_SAMPLES, path)
            result = session.load(path)
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, result[0])


# ---------------------------------------------------------------------------
# run() — fully mocked
# ---------------------------------------------------------------------------

def _run_with_mocks(config=None):
    """
    Call CalibrationSession.run() with all external dependencies mocked:
      - cv2.VideoCapture (cap) — always returns a black frame
      - FaceMeshTracker.process() — returns synthetic mesh arrays
      - HeadPoseEstimator.estimate() — returns fixed (pitch, yaw, roll)
      - get_iris_positions() — returns fixed iris dict
      - pyautogui.size() — returns (1920, 1080)
      - CalibrationUI — replaced with a MagicMock (no tkinter)
    """
    if config is None:
        config = MINIMAL_CONFIG

    from src.calibration.calibration import CalibrationSession

    session = CalibrationSession(config)

    mesh_points, mesh_points_3d = _build_mock_mesh()
    mock_tracker = MagicMock()
    mock_tracker.process.return_value = (mesh_points, mesh_points_3d)

    mock_head_pose = MagicMock()
    mock_head_pose.estimate.return_value = (2.0, -1.5, 0.0)

    mock_cap = MagicMock()
    black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    mock_cap.read.return_value = (True, black_frame)

    iris_return = _mock_iris_return()

    with patch('src.calibration.calibration.CalibrationUI') as mock_ui_cls, \
         patch('src.calibration.calibration.get_iris_positions',
               return_value=iris_return), \
         patch('src.calibration.calibration.pyautogui.size',
               return_value=(1920, 1080)):

        mock_ui_instance = MagicMock()
        mock_ui_cls.return_value = mock_ui_instance

        samples = session.run(mock_cap, mock_tracker, mock_head_pose)

    return samples, mock_ui_instance


class TestCalibrationSessionRunReturnType(unittest.TestCase):
    """run() returns a list of dicts."""

    def test_result_is_list(self):
        samples, _ = _run_with_mocks()
        self.assertIsInstance(samples, list)

    def test_result_length_is_nine(self):
        samples, _ = _run_with_mocks()
        self.assertEqual(len(samples), 9)


class TestCalibrationSessionRunSampleKeys(unittest.TestCase):
    """Each sample dict contains all required keys."""

    EXPECTED_KEYS = {'iris_dx', 'iris_dy', 'pitch', 'yaw', 'screen_x', 'screen_y'}

    def test_first_sample_has_all_keys(self):
        samples, _ = _run_with_mocks()
        for key in self.EXPECTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, samples[0])

    def test_last_sample_has_all_keys(self):
        samples, _ = _run_with_mocks()
        for key in self.EXPECTED_KEYS:
            with self.subTest(key=key):
                self.assertIn(key, samples[8])


class TestCalibrationSessionRunIrisDxValue(unittest.TestCase):
    """iris_dx is the mean of mocked l_dx and r_dx."""

    def test_iris_dx_is_average_of_l_and_r_dx(self):
        # l_dx=5, r_dx=5 → avg = 5.0
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['iris_dx'], 5.0)

    def test_iris_dy_is_average_of_l_and_r_dy(self):
        # l_dy=2, r_dy=2 → avg = 2.0
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['iris_dy'], 2.0)


class TestCalibrationSessionRunPitchYaw(unittest.TestCase):
    """pitch and yaw come from head_pose.estimate()."""

    def test_pitch_matches_mock_estimate(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['pitch'], 2.0)

    def test_yaw_matches_mock_estimate(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['yaw'], -1.5)


class TestCalibrationSessionRunScreenCoords(unittest.TestCase):
    """
    screen_x and screen_y are the grid positions derived from pyautogui.size().
    With size (1920, 1080):
      x positions = [0.1*1920, 0.5*1920, 0.9*1920] = [192, 960, 1728]
      y positions = [0.1*1080, 0.5*1080, 0.9*1080] = [108, 540, 972]
    Grid is row-major: (x0,y0),(x1,y0),(x2,y0),(x0,y1),...
    """

    def test_first_point_screen_x(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['screen_x'], 0.1 * 1920)

    def test_first_point_screen_y(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[0]['screen_y'], 0.1 * 1080)

    def test_second_point_screen_x_is_centre(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[1]['screen_x'], 0.5 * 1920)

    def test_fifth_point_is_centre_of_screen(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[4]['screen_x'], 0.5 * 1920)
        self.assertAlmostEqual(samples[4]['screen_y'], 0.5 * 1080)

    def test_last_point_screen_x(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[8]['screen_x'], 0.9 * 1920)

    def test_last_point_screen_y(self):
        samples, _ = _run_with_mocks()
        self.assertAlmostEqual(samples[8]['screen_y'], 0.9 * 1080)


class TestCalibrationSessionRunUIInteraction(unittest.TestCase):
    """CalibrationUI is instantiated once and show_point is called for each point."""

    def test_calibration_ui_instantiated_once(self):
        with patch('src.calibration.calibration.CalibrationUI') as mock_ui_cls, \
             patch('src.calibration.calibration.get_iris_positions',
                   return_value=_mock_iris_return()), \
             patch('src.calibration.calibration.pyautogui.size',
                   return_value=(1920, 1080)):

            mock_ui_cls.return_value = MagicMock()
            session = _make_session()
            mesh_points, mesh_points_3d = _build_mock_mesh()
            mock_tracker = MagicMock()
            mock_tracker.process.return_value = (mesh_points, mesh_points_3d)
            mock_head_pose = MagicMock()
            mock_head_pose.estimate.return_value = (2.0, -1.5, 0.0)
            mock_cap = MagicMock()
            mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

            session.run(mock_cap, mock_tracker, mock_head_pose)

        mock_ui_cls.assert_called_once()

    def test_show_point_called_nine_times(self):
        with patch('src.calibration.calibration.CalibrationUI') as mock_ui_cls, \
             patch('src.calibration.calibration.get_iris_positions',
                   return_value=_mock_iris_return()), \
             patch('src.calibration.calibration.pyautogui.size',
                   return_value=(1920, 1080)):

            mock_ui_instance = MagicMock()
            mock_ui_cls.return_value = mock_ui_instance
            session = _make_session()
            mesh_points, mesh_points_3d = _build_mock_mesh()
            mock_tracker = MagicMock()
            mock_tracker.process.return_value = (mesh_points, mesh_points_3d)
            mock_head_pose = MagicMock()
            mock_head_pose.estimate.return_value = (2.0, -1.5, 0.0)
            mock_cap = MagicMock()
            mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

            session.run(mock_cap, mock_tracker, mock_head_pose)

        self.assertEqual(mock_ui_instance.show_point.call_count, 9)

    def test_ui_close_called_after_run(self):
        """CalibrationUI.close() is called at least once (hide after run)."""
        _, mock_ui = _run_with_mocks()
        mock_ui.close.assert_called()


class TestCalibrationSessionRunCameraFailure(unittest.TestCase):
    """run() raises RuntimeError if camera read fails during calibration."""

    def test_camera_read_failure_raises_runtime_error(self):
        from src.calibration.calibration import CalibrationSession
        session = CalibrationSession(MINIMAL_CONFIG)

        mock_tracker = MagicMock()
        mesh_points, mesh_points_3d = _build_mock_mesh()
        mock_tracker.process.return_value = (mesh_points, mesh_points_3d)
        mock_head_pose = MagicMock()
        mock_head_pose.estimate.return_value = (2.0, -1.5, 0.0)

        mock_cap = MagicMock()
        mock_cap.read.return_value = (False, None)  # camera failure

        with patch('src.calibration.calibration.CalibrationUI') as mock_ui_cls, \
             patch('src.calibration.calibration.get_iris_positions',
                   return_value=_mock_iris_return()), \
             patch('src.calibration.calibration.pyautogui.size',
                   return_value=(1920, 1080)):

            mock_ui_cls.return_value = MagicMock()

            with self.assertRaises(RuntimeError):
                session.run(mock_cap, mock_tracker, mock_head_pose)


class TestCalibrationSessionRunNoFaceSkipsFrame(unittest.TestCase):
    """
    If tracker.process() returns None (no face detected), the frame is skipped
    and the loop continues until collect_frames valid frames are collected.
    """

    def test_no_face_frames_are_skipped_and_run_completes(self):
        """
        Return None for the first call to process(), then valid mesh data.
        run() must complete successfully (9 samples) rather than crashing.
        """
        from src.calibration.calibration import CalibrationSession

        config = dict(MINIMAL_CONFIG)
        config['calibration_collect_frames'] = 2
        session = CalibrationSession(config)

        mesh_points, mesh_points_3d = _build_mock_mesh()
        mock_tracker = MagicMock()
        # First call returns None (no face), subsequent calls return valid data
        mock_tracker.process.side_effect = (
            [None] + [( mesh_points, mesh_points_3d)] * 200
        )

        mock_head_pose = MagicMock()
        mock_head_pose.estimate.return_value = (2.0, -1.5, 0.0)

        mock_cap = MagicMock()
        mock_cap.read.return_value = (True, np.zeros((480, 640, 3), dtype=np.uint8))

        with patch('src.calibration.calibration.CalibrationUI') as mock_ui_cls, \
             patch('src.calibration.calibration.get_iris_positions',
                   return_value=_mock_iris_return()), \
             patch('src.calibration.calibration.pyautogui.size',
                   return_value=(1920, 1080)):

            mock_ui_cls.return_value = MagicMock()
            samples = session.run(mock_cap, mock_tracker, mock_head_pose)

        self.assertEqual(len(samples), 9)


if __name__ == "__main__":
    unittest.main()
