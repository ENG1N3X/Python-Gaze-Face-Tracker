import cv2
import numpy as np

LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]
LEFT_EYE_OUTER_CORNER = [33]
LEFT_EYE_INNER_CORNER = [133]
RIGHT_EYE_OUTER_CORNER = [362]
RIGHT_EYE_INNER_CORNER = [263]
RIGHT_EYE_POINTS = [33, 160, 159, 158, 133, 153, 145, 144]
LEFT_EYE_POINTS = [362, 385, 386, 387, 263, 373, 374, 380]


def _vector_position(point1, point2):
    x1, y1 = point1.ravel()
    x2, y2 = point2.ravel()
    return x2 - x1, y2 - y1


def get_iris_positions(mesh_points: np.ndarray) -> dict:
    (l_cx, l_cy), l_radius = cv2.minEnclosingCircle(mesh_points[LEFT_IRIS])
    (r_cx, r_cy), r_radius = cv2.minEnclosingCircle(mesh_points[RIGHT_IRIS])
    center_left = np.array([l_cx, l_cy], dtype=np.float32)
    center_right = np.array([r_cx, r_cy], dtype=np.float32)
    l_dx, l_dy = _vector_position(mesh_points[LEFT_EYE_OUTER_CORNER], center_left)
    r_dx, r_dy = _vector_position(mesh_points[RIGHT_EYE_OUTER_CORNER], center_right)
    return {
        "l_center": center_left,
        "r_center": center_right,
        "l_cx": l_cx, "l_cy": l_cy,
        "r_cx": r_cx, "r_cy": r_cy,
        "l_dx": l_dx, "l_dy": l_dy,
        "r_dx": r_dx, "r_dy": r_dy,
        "l_radius": l_radius,
        "r_radius": r_radius,
    }
