"""
Eye Tracking and Head Pose Estimation

Refactored orchestrator — Phase 0.
Original author: Alireza Bagheri
GitHub: https://github.com/alireza787b/Python-Gaze-Face-Tracker
"""

import csv
import logging
import os
import socket
import warnings

# Suppress deprecation warning from mediapipe internals (protobuf SymbolDatabase)
warnings.filterwarnings("ignore", message="SymbolDatabase.GetPrototype", category=UserWarning)
import argparse
import time
from datetime import datetime

import cv2 as cv
import numpy as np

logger = logging.getLogger(__name__)

from src.utils.config import load_config
from src.calibration.calibration import CalibrationSession
from src.calibration.mapping import GazeMapper
from src.tracking.face_mesh import FaceMeshTracker
from src.tracking.iris_tracker import (
    get_iris_positions,
    LEFT_IRIS, RIGHT_IRIS,
    LEFT_EYE_OUTER_CORNER, LEFT_EYE_INNER_CORNER,
    RIGHT_EYE_OUTER_CORNER, RIGHT_EYE_INNER_CORNER,
)
from src.tracking.blink_detector import BlinkDetector
from src.tracking.head_pose import HeadPoseEstimator
from src.tracking.iris_filter import IrisFilter
from src.control.cursor import CursorController
from src.control.clicker import DoubleBlinkClicker
from src.control.mouse_monitor import MouseMonitor


def main():
    config = load_config("config/default_config.json")

    PRINT_DATA = config["print_data"]
    SHOW_ALL_FEATURES = config["show_all_features"]
    LOG_DATA = config["log_data"]
    LOG_ALL_FEATURES = config["log_all_features"]
    SHOW_ON_SCREEN_DATA = config["show_on_screen_data"]
    ENABLE_HEAD_POSE = config["enable_head_pose"]
    LOG_FOLDER = config["log_folder"]
    SERVER_ADDRESS = (config["server_ip"], config["server_port"])

    parser = argparse.ArgumentParser(description="Eye Tracking Application")
    parser.add_argument("-c", "--camSource", help="Source of camera", default=str(config["camera_index"]))
    args = parser.parse_args()

    if PRINT_DATA:
        print("Initializing the face mesh and camera...")
        head_pose_status = "enabled" if ENABLE_HEAD_POSE else "disabled"
        print(f"Head pose estimation is {head_pose_status}.")

    print("\nControls:")
    print("  [C] Reset head pose   — saves current head position as the 'zero' baseline")
    print("                          Pitch/yaw for scroll control are measured relative to this point.")
    print("                          Press while looking straight ahead for best results.")
    print("  [R] Recalibrate gaze  — runs the full 9-point gaze calibration process")
    print("  [P] Toggle cursor     — enable/disable gaze cursor control")
    print("  [S] Toggle recording  — start/stop CSV logging")
    print("  [Q] Quit\n")

    tracker = FaceMeshTracker(config)
    blink_detector = BlinkDetector(config)
    head_pose = HeadPoseEstimator(config)
    cursor_controller = CursorController(config)
    iris_filter = IrisFilter(config)
    clicker = DoubleBlinkClicker(config)
    mouse_monitor = MouseMonitor(config)
    prev_manual_active = False
    click_indicator_until = 0.0
    head_reset_indicator_until = 0.0

    cap = cv.VideoCapture(int(args.camSource))
    iris_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    # Calibration bootstrap
    calibration_session = CalibrationSession(config)
    gaze_mapper = GazeMapper()
    calib_path = config["calibration_path"]

    try:
        loaded = gaze_mapper.load(calib_path)
    except Exception as e:
        print(f"Calibration file error ({e}), running new calibration...")
        loaded = False

    if not loaded:
        print("No calibration found. Running calibration...")
        samples = calibration_session.run(cap, tracker, head_pose, blink_detector)
        gaze_mapper.fit(samples)
        gaze_mapper.save(calib_path, samples)
        print("Calibration complete.")
    else:
        print(f"Calibration loaded from {calib_path}")

    os.makedirs(LOG_FOLDER, exist_ok=True)
    csv_data = []
    IS_RECORDING = False

    column_names = [
        "Timestamp (ms)", "Left Eye Center X", "Left Eye Center Y",
        "Right Eye Center X", "Right Eye Center Y",
        "Left Iris Relative Pos Dx", "Left Iris Relative Pos Dy",
        "Right Iris Relative Pos Dx", "Right Iris Relative Pos Dy",
        "Total Blink Count",
    ]
    if ENABLE_HEAD_POSE:
        column_names.extend(["Pitch", "Yaw", "Roll"])
    if LOG_ALL_FEATURES:
        column_names.extend(
            [f"Landmark_{i}_X" for i in range(468)] +
            [f"Landmark_{i}_Y" for i in range(468)]
        )

    # pitch/yaw/roll placeholders for on-screen display
    pitch, yaw, roll = 0.0, 0.0, 0.0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            img_h, img_w = frame.shape[:2]
            result = tracker.process(frame)

            if result is not None:
                mesh_points, mesh_points_3d = result

                # Blink detection
                blink_detected = blink_detector.update(mesh_points_3d)
                if clicker.update(blink_detected):
                    click_indicator_until = time.monotonic() + 0.3

                # Iris positions
                iris = get_iris_positions(mesh_points)
                l_cx, l_cy = iris["l_cx"], iris["l_cy"]
                r_cx, r_cy = iris["r_cx"], iris["r_cy"]
                l_dx, l_dy = iris["l_dx"], iris["l_dy"]
                r_dx, r_dy = iris["r_dx"], iris["r_dy"]
                center_left = iris["l_center"]
                center_right = iris["r_center"]
                l_radius = iris["l_radius"]
                r_radius = iris["r_radius"]

                # Head pose — display approach (Approach A, always runs)
                if ENABLE_HEAD_POSE:
                    display_pose = head_pose.estimate_display(mesh_points_3d, mesh_points, (img_h, img_w))
                    angle_x = display_pose["angle_x"]
                    angle_y = display_pose["angle_y"]
                    face_looks = display_pose["face_looks"]
                    nose_p1 = display_pose["nose_p1"]
                    nose_p2 = display_pose["nose_p2"]

                    if SHOW_ON_SCREEN_DATA:
                        cv.putText(frame, f"Face Looking at {face_looks}",
                                   (img_w - 400, 80), cv.FONT_HERSHEY_TRIPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
                    cv.line(frame, tuple(nose_p1.tolist()), tuple(nose_p2), (255, 0, 255), 3)

                # Head pose — calibrated approach (Approach B)
                if ENABLE_HEAD_POSE:
                    pitch, yaw, roll = head_pose.estimate(mesh_points, (img_h, img_w))

                # Cursor control
                manual_active = mouse_monitor.check()
                if prev_manual_active and not manual_active:
                    cursor_controller.reset_buffer()
                    iris_filter.reset()
                prev_manual_active = manual_active
                if gaze_mapper.is_calibrated() and not manual_active:
                    iris_dx = (iris["l_dx"] + iris["r_dx"]) / 2.0
                    iris_dy = (iris["l_dy"] + iris["r_dy"]) / 2.0
                    iris_dx, iris_dy = iris_filter.update(iris_dx, iris_dy)
                    try:
                        pred_x, pred_y = gaze_mapper.predict(iris_dx, iris_dy, pitch, yaw)
                        pos = cursor_controller.move(pred_x, pred_y)
                        if pos:
                            mouse_monitor.record_gaze_move(*pos)
                    except Exception as e:
                        logger.error("Gaze prediction failed: %s", e)
                else:
                    mouse_monitor.sync_position()

                if PRINT_DATA:
                    print(f"Total Blinks: {blink_detector.total_blinks}")
                    print(f"Left Eye Center X: {l_cx} Y: {l_cy}")
                    print(f"Right Eye Center X: {r_cx} Y: {r_cy}")
                    print(f"Left Iris Relative Pos Dx: {l_dx} Dy: {l_dy}")
                    print(f"Right Iris Relative Pos Dx: {r_dx} Dy: {r_dy}\n")
                    if ENABLE_HEAD_POSE:
                        print(f"Head Pose Angles: Pitch={pitch}, Yaw={yaw}, Roll={roll}")

                # Show all facial landmarks
                if SHOW_ALL_FEATURES:
                    for point in mesh_points:
                        cv.circle(frame, tuple(point), 1, (0, 255, 0), -1)

                # Draw irises and eye corners
                cv.circle(frame, (int(center_left[0]), int(center_left[1])), int(l_radius), (255, 0, 255), 2, cv.LINE_AA)
                cv.circle(frame, (int(center_right[0]), int(center_right[1])), int(r_radius), (255, 0, 255), 2, cv.LINE_AA)
                cv.circle(frame, mesh_points[LEFT_EYE_INNER_CORNER[0]], 3, (255, 255, 255), -1, cv.LINE_AA)
                cv.circle(frame, mesh_points[LEFT_EYE_OUTER_CORNER[0]], 3, (0, 255, 255), -1, cv.LINE_AA)
                cv.circle(frame, mesh_points[RIGHT_EYE_INNER_CORNER[0]], 3, (255, 255, 255), -1, cv.LINE_AA)
                cv.circle(frame, mesh_points[RIGHT_EYE_OUTER_CORNER[0]], 3, (0, 255, 255), -1, cv.LINE_AA)

                # Logging
                if LOG_DATA:
                    timestamp = int(time.time() * 1000)
                    log_entry = [
                        timestamp, l_cx, l_cy, r_cx, r_cy,
                        l_dx, l_dy, r_dx, r_dy,
                        blink_detector.total_blinks,
                    ]
                    if ENABLE_HEAD_POSE:
                        log_entry.extend([pitch, yaw, roll])
                    if LOG_ALL_FEATURES:
                        log_entry.extend([p for point in mesh_points for p in point])
                    csv_data.append(log_entry)

                # UDP send
                timestamp = int(time.time() * 1000)
                packet = (np.array([timestamp], dtype=np.int64).tobytes() +
                          np.array([l_cx, l_cy, l_dx, l_dy], dtype=np.int32).tobytes())
                iris_socket.sendto(packet, SERVER_ADDRESS)
                if PRINT_DATA:
                    print(f'Sent UDP packet to {SERVER_ADDRESS}: {packet}')

                # On-screen data
                if SHOW_ON_SCREEN_DATA:
                    if IS_RECORDING:
                        cv.circle(frame, (30, 30), 10, (0, 0, 255), -1)
                    cv.putText(frame, f"Blinks: {blink_detector.total_blinks}",
                               (30, 80), cv.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
                    if ENABLE_HEAD_POSE:
                        cv.putText(frame, f"Pitch: {int(pitch)}", (30, 110), cv.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
                        cv.putText(frame, f"Yaw: {int(yaw)}", (30, 140), cv.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
                        cv.putText(frame, f"Roll: {int(roll)}", (30, 170), cv.FONT_HERSHEY_DUPLEX, 0.8, (0, 255, 0), 2, cv.LINE_AA)
                    if time.monotonic() < click_indicator_until:
                        cv.putText(frame, "CLICK", (30, 210), cv.FONT_HERSHEY_DUPLEX, 0.8, (0, 220, 255), 2, cv.LINE_AA)
                    if time.monotonic() < head_reset_indicator_until:
                        msg = "Head pose reset  look straight ahead"
                        (w, h), _ = cv.getTextSize(msg, cv.FONT_HERSHEY_DUPLEX, 0.7, 2)
                        x = (img_w - w) // 2
                        y = img_h // 2
                        cv.rectangle(frame, (x - 8, y - h - 8), (x + w + 8, y + 8), (0, 0, 0), -1)
                        cv.putText(frame, msg, (x, y), cv.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 128), 2, cv.LINE_AA)

                    # Controls hint — bottom right corner
                    cursor_state = "ON" if cursor_controller.is_enabled() else "OFF"
                    controls = [
                        f"[P] Cursor: {cursor_state}",
                        "[R] Recalibrate",
                        "[C] Reset head pose",
                        "[S] Recording",
                        "[Q] Quit",
                    ]
                    font = cv.FONT_HERSHEY_SIMPLEX
                    font_scale = 0.5
                    thickness = 1
                    line_h = 20
                    margin = 10
                    for i, text in enumerate(reversed(controls)):
                        y = img_h - margin - i * line_h
                        # dark shadow for readability
                        cv.putText(frame, text, (img_w - 210, y + 1), font, font_scale, (0, 0, 0), thickness + 1, cv.LINE_AA)
                        cv.putText(frame, text, (img_w - 210, y), font, font_scale, (200, 200, 200), thickness, cv.LINE_AA)

            cv.imshow("Eye Tracking", frame)
            key = cv.waitKey(1) & 0xFF

            if key == ord('c'):
                head_pose.recalibrate()
                head_reset_indicator_until = time.monotonic() + 2.0
                print("Head pose reset. Current position saved as zero baseline.")

            if key == ord('s'):
                IS_RECORDING = not IS_RECORDING
                print("Recording started." if IS_RECORDING else "Recording paused.")

            if key == ord('r'):
                head_pose.recalibrate()
                head_reset_indicator_until = time.monotonic() + 2.0
                print("Head pose reset. Current position saved as zero baseline.")
                print("Starting recalibration...")
                samples = calibration_session.run(cap, tracker, head_pose, blink_detector)
                gaze_mapper.fit(samples)
                gaze_mapper.save(calib_path, samples)
                print("Recalibration complete.")

            if key == ord('p'):
                cursor_controller.set_enabled(not cursor_controller.is_enabled())
                state = "enabled" if cursor_controller.is_enabled() else "paused"
                print(f"Cursor control {state}.")

            if key == ord('q'):
                if PRINT_DATA:
                    print("Exiting program...")
                break

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        cap.release()
        cv.destroyAllWindows()
        iris_socket.close()
        tracker.close()
        mouse_monitor.stop()
        if PRINT_DATA:
            print("Program exited successfully.")
        if LOG_DATA and IS_RECORDING:
            if PRINT_DATA:
                print("Writing data to CSV...")
            timestamp_str = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
            csv_file_name = os.path.join(LOG_FOLDER, f"eye_tracking_log_{timestamp_str}.csv")
            with open(csv_file_name, "w", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(column_names)
                writer.writerows(csv_data)
            if PRINT_DATA:
                print(f"Data written to {csv_file_name}")


if __name__ == "__main__":
    main()
