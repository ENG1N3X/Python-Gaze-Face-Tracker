import os
import json
import pickle
import base64
from datetime import datetime

import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
from sklearn.linear_model import Ridge


class GazeMapper:
    def __init__(self) -> None:
        self._calibrated = False
        self._pipeline = None

    def fit(self, samples: list) -> None:
        if len(samples) < 4:
            raise ValueError(f"Need at least 4 samples, got {len(samples)}")
        X = np.array([[s['iris_dx'], s['iris_dy'], s['pitch'], s['yaw']] for s in samples])
        Y = np.array([[s['screen_x'], s['screen_y']] for s in samples])
        self._pipeline = Pipeline([
            ('poly', PolynomialFeatures(degree=2, include_bias=False)),
            ('ridge', Ridge(alpha=1.0)),
        ])
        self._pipeline.fit(X, Y)
        self._calibrated = True

    def predict(self, iris_dx: float, iris_dy: float, pitch: float, yaw: float) -> tuple:
        if not self._calibrated:
            raise RuntimeError("GazeMapper is not calibrated")
        x = np.array([[iris_dx, iris_dy, pitch, yaw]])
        pred = self._pipeline.predict(x)
        return float(pred[0, 0]), float(pred[0, 1])

    def is_calibrated(self) -> bool:
        return self._calibrated

    def save(self, path: str, samples: list = None) -> None:
        if not self._calibrated:
            raise RuntimeError("GazeMapper is not calibrated — call fit() first")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        pipeline_bytes = pickle.dumps(self._pipeline)
        pipeline_b64 = base64.b64encode(pipeline_bytes).decode('utf-8')
        data = {
            'version': 1,
            'created_at': datetime.now().isoformat(),
            'pipeline_b64': pipeline_b64,
            'samples': samples if samples is not None else [],
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        with open(path, 'r') as f:
            data = json.load(f)
        pipeline_bytes = base64.b64decode(data['pipeline_b64'])
        self._pipeline = pickle.loads(pipeline_bytes)
        self._calibrated = True
        return True
