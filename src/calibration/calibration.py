import os
import json
from datetime import datetime

import cv2
import pyautogui

from src.tracking.face_mesh import FaceMeshTracker
from src.tracking.iris_tracker import get_iris_positions
from src.tracking.head_pose import HeadPoseEstimator
from src.tracking.blink_detector import BlinkDetector
from src.tracking.fixation_detector import GazeFixationDetector
from src.ui.calibration_ui import CalibrationUI


class CalibrationSession:
    def __init__(self, config: dict) -> None:
        self._n_points = config['calibration_points']
        self._collect_frames = config['calibration_collect_frames']
        self._config = config
        # Pre-create Tk before OpenCV's cv.imshow() ever runs — avoids the
        # macOS AppKit conflict that crashes Tk 8.6 on newer macOS versions.
        # CalibrationUI.__init__ calls withdraw() immediately, so no window appears.
        self._ui = CalibrationUI()

    def run(
        self,
        cap: cv2.VideoCapture,
        tracker: FaceMeshTracker,
        head_pose: HeadPoseEstimator,
        blink_detector: BlinkDetector | None = None,
    ) -> list:
        screen_w, screen_h = pyautogui.size()
        x_positions = [screen_w * r for r in [0.1, 0.5, 0.9]]
        y_positions = [screen_h * r for r in [0.1, 0.5, 0.9]]
        grid_points = [(x, y) for y in y_positions for x in x_positions]

        self._ui.show()  # reuse the pre-created Tk instance

        ui = self._ui
        samples = []
        fixation = GazeFixationDetector(self._config)
        min_shift = self._config.get("calibration_gaze_shift_px", 3)

        # iris position after the previous point's fixation (None for first point)
        prev_iris_dx: float | None = None
        prev_iris_dy: float | None = None

        try:
            for i, (pt_x, pt_y) in enumerate(grid_points):
                ui.show_point(i, self._n_points, int(pt_x), int(pt_y))
                fixation.reset()
                # First point: no shift required. Subsequent: user must move gaze.
                has_shifted = (prev_iris_dx is None)

                # Phase 1 — wait for gaze shift (if needed) then fixation
                while not fixation.is_fixated():
                    ret, frame = cap.read()
                    if not ret:
                        raise RuntimeError("Camera read failed during calibration")
                    result = tracker.process(frame)
                    if result is None:
                        ui.update_hint("Look at the dot...", 'gray')
                        ui.update_stability(0)
                        ui.tick()
                        continue
                    mesh_points, mesh_points_3d = result
                    img_h, img_w = frame.shape[:2]

                    # Eyes must be open — closed eyes produce fake stable iris coords
                    if blink_detector and not blink_detector.is_eyes_open(mesh_points_3d):
                        fixation.reset()
                        ui.update_hint("Open your eyes!", 'red')
                        ui.update_stability(0)
                        ui.tick()
                        continue

                    iris = get_iris_positions(mesh_points)
                    iris_dx = (iris['l_dx'] + iris['r_dx']) / 2.0
                    iris_dy = (iris['l_dy'] + iris['r_dy']) / 2.0

                    # Require gaze to shift from previous fixation point
                    if not has_shifted:
                        shift = abs(iris_dx - prev_iris_dx) + abs(iris_dy - prev_iris_dy)
                        if shift < min_shift:
                            fixation.reset()
                            ui.update_hint("Look at the NEW dot!", 'yellow')
                            ui.update_stability(0)
                            ui.tick()
                            continue
                        has_shifted = True
                        fixation.reset()  # start fresh after confirmed shift

                    fixation.update(iris_dx, iris_dy)
                    progress = fixation.progress()
                    if progress > 0.5:
                        ui.update_hint("Hold still...", 'white')
                    else:
                        ui.update_hint("Look at the dot...", 'gray')
                    ui.update_stability(progress)
                    ui.tick()

                # Record iris position of this fixation for next point's shift check
                prev_iris_dx = iris_dx
                prev_iris_dy = iris_dy

                # Phase 2 — collect frames (skip frames where eyes are closed)
                ui.update_stability(0)
                iris_dx_vals, iris_dy_vals, pitch_vals, yaw_vals = [], [], [], []
                frames_collected = 0
                while frames_collected < self._collect_frames:
                    ret, frame = cap.read()
                    if not ret:
                        raise RuntimeError("Camera read failed during calibration")
                    result = tracker.process(frame)
                    if result is None:
                        ui.tick()
                        continue
                    mesh_points, mesh_points_3d = result
                    img_h, img_w = frame.shape[:2]

                    # Skip frames where eyes are closed
                    if blink_detector and not blink_detector.is_eyes_open(mesh_points_3d):
                        ui.update_hint("Keep eyes open!", 'red')
                        ui.tick()
                        continue

                    ui.update_hint("", 'gray')
                    ui.update_countdown(frames_collected / self._collect_frames)
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
