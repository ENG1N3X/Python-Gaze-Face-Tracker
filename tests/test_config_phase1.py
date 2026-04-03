"""
Tests for Phase 1 additions to config/default_config.json

Acceptance criteria covered (Phase 1 — F5 Configuration):
- load_config("config/default_config.json") returns a dict that contains
  the Phase 1 keys: calibration_path, calibration_collect_frames
- calibration_path value equals "data/calibration.json"
- calibration_collect_frames is an integer > 0
- calibration_dwell_sec is a positive number (pre-existing, Phase 1 relies on it)
- calibration_points equals 9 (pre-existing, Phase 1 relies on it)
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "default_config.json")


class TestPhase1ConfigKeyCalibrationPath(unittest.TestCase):
    """calibration_path key is present in default_config.json."""

    def test_calibration_path_key_present(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIn("calibration_path", config)

    def test_calibration_path_value_is_string(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIsInstance(config["calibration_path"], str)

    def test_calibration_path_value_equals_expected(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertEqual(config["calibration_path"], "data/calibration.json")


class TestPhase1ConfigKeyCalibrationCollectFrames(unittest.TestCase):
    """calibration_collect_frames key is present and valid."""

    def test_calibration_collect_frames_key_present(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIn("calibration_collect_frames", config)

    def test_calibration_collect_frames_is_integer(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIsInstance(config["calibration_collect_frames"], int)

    def test_calibration_collect_frames_is_positive(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertGreater(config["calibration_collect_frames"], 0)


class TestPhase1ConfigPreExistingCalibrationKeys(unittest.TestCase):
    """Phase 1 relies on keys that were already in the config before Phase 1."""

    def test_calibration_dwell_sec_is_present(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIn("calibration_dwell_sec", config)

    def test_calibration_dwell_sec_is_positive(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertGreater(config["calibration_dwell_sec"], 0)

    def test_calibration_points_is_present(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertIn("calibration_points", config)

    def test_calibration_points_equals_nine(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertEqual(config["calibration_points"], 9)


class TestPhase1ConfigCalibrationPathPointsToDataDir(unittest.TestCase):
    """calibration_path starts with 'data/' — the gitignored data directory."""

    def test_calibration_path_starts_with_data_dir(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertTrue(config["calibration_path"].startswith("data/"))

    def test_calibration_path_ends_with_json(self):
        from src.utils.config import load_config
        config = load_config(DEFAULT_CONFIG_PATH)
        self.assertTrue(config["calibration_path"].endswith(".json"))


if __name__ == "__main__":
    unittest.main()
