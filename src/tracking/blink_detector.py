import numpy as np
from src.tracking.iris_tracker import RIGHT_EYE_POINTS, LEFT_EYE_POINTS


class BlinkDetector:
    def __init__(self, config: dict) -> None:
        self._threshold = config["blink_threshold"]
        self._consec_frames = config["blink_consec_frames"]
        self._frame_counter = 0
        self._total_blinks = 0

    def is_eyes_open(self, mesh_points_3d: np.ndarray) -> bool:
        """Return True if both eyes are open (EAR above blink threshold)."""
        return self._blinking_ratio(mesh_points_3d) > self._threshold

    def update(self, mesh_points_3d: np.ndarray) -> bool:
        blink_detected = False
        ear = self._blinking_ratio(mesh_points_3d)
        if ear <= self._threshold:
            self._frame_counter += 1
        else:
            if self._frame_counter > self._consec_frames:
                self._total_blinks += 1
                blink_detected = True
            self._frame_counter = 0
        return blink_detected

    @property
    def total_blinks(self) -> int:
        return self._total_blinks

    def _euclidean_distance_3d(self, points) -> float:
        P0, P3, P4, P5, P8, P11, P12, P13 = points
        numerator = (
            np.linalg.norm(P3 - P13) ** 3
            + np.linalg.norm(P4 - P12) ** 3
            + np.linalg.norm(P5 - P11) ** 3
        )
        denominator = 3 * np.linalg.norm(P0 - P8) ** 3
        return numerator / denominator

    def _blinking_ratio(self, mesh_points_3d: np.ndarray) -> float:
        right_ratio = self._euclidean_distance_3d(mesh_points_3d[RIGHT_EYE_POINTS])
        left_ratio = self._euclidean_distance_3d(mesh_points_3d[LEFT_EYE_POINTS])
        return (right_ratio + left_ratio + 1) / 2
