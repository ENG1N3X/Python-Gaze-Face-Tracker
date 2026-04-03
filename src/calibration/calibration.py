import os
import json
from datetime import datetime

import cv2
import pyautogui

from src.tracking.face_mesh import FaceMeshTracker
from src.tracking.iris_tracker import get_iris_positions
from src.tracking.head_pose import HeadPoseEstimator
from src.ui.calibration_ui import CalibrationUI


class CalibrationSession:
    def __init__(self, config: dict) -> None:
        self._dwell_sec = config['calibration_dwell_sec']
        self._n_points = config['calibration_points']
        self._collect_frames = config['calibration_collect_frames']

    def run(
        self,
        cap: cv2.VideoCapture,
        tracker: FaceMeshTracker,
        head_pose: HeadPoseEstimator,
    ) -> list:
        screen_w, screen_h = pyautogui.size()
        x_positions = [screen_w * r for r in [0.1, 0.5, 0.9]]
        y_positions = [screen_h * r for r in [0.1, 0.5, 0.9]]
        grid_points = [(x, y) for y in y_positions for x in x_positions]

        ui = CalibrationUI()
        samples = []

        try:
            for i, (pt_x, pt_y) in enumerate(grid_points):
                ui.show_point(i, self._n_points, int(pt_x), int(pt_y))

                # Discard frames (dwell/settle period — no countdown yet)
                frames_discarded = 0
                while frames_discarded < self._collect_frames:
                    ret, frame = cap.read()
                    if not ret:
                        raise RuntimeError("Camera read failed during calibration")
                    result = tracker.process(frame)
                    if result is None:
                        continue
                    frames_discarded += 1

                # Collect frames (countdown shown here)
                iris_dx_vals, iris_dy_vals, pitch_vals, yaw_vals = [], [], [], []
                frames_collected = 0
                while frames_collected < self._collect_frames:
                    ret, frame = cap.read()
                    if not ret:
                        raise RuntimeError("Camera read failed during calibration")
                    result = tracker.process(frame)
                    if result is None:
                        continue
                    ui.update_countdown(frames_collected / self._collect_frames)
                    mesh_points, mesh_points_3d = result
                    img_h, img_w = frame.shape[:2]
                    iris = get_iris_positions(mesh_points)
                    iris_dx = (iris['l_dx'] + iris['r_dx']) / 2.0
                    iris_dy = (iris['l_dy'] + iris['r_dy']) / 2.0
                    pitch, yaw, _ = head_pose.estimate(mesh_points, (img_h, img_w))
                    iris_dx_vals.append(iris_dx)
                    iris_dy_vals.append(iris_dy)
                    pitch_vals.append(pitch)
                    yaw_vals.append(yaw)
                    frames_collected += 1

                samples.append({
                    'iris_dx': float(sum(iris_dx_vals) / len(iris_dx_vals)),
                    'iris_dy': float(sum(iris_dy_vals) / len(iris_dy_vals)),
                    'pitch': float(sum(pitch_vals) / len(pitch_vals)),
                    'yaw': float(sum(yaw_vals) / len(yaw_vals)),
                    'screen_x': float(pt_x),
                    'screen_y': float(pt_y),
                })
        finally:
            ui.close()

        return samples

    def save(self, samples: list, path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        data = {
            'version': 1,
            'created_at': datetime.now().isoformat(),
            'samples': samples,
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self, path: str):
        if not os.path.exists(path):
            return None
        with open(path, 'r') as f:
            data = json.load(f)
        return data.get('samples')
