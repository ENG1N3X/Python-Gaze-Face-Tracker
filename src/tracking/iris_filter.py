import collections

import numpy as np


class IrisFilter:
    """Rolling median filter with single-frame spike rejection for iris dx/dy."""

    def __init__(self, config: dict) -> None:
        window = config.get("iris_filter_window", 5)
        self._spike_threshold = config.get("iris_spike_threshold_px", 8.0)
        self._dx_buf: collections.deque = collections.deque(maxlen=window)
        self._dy_buf: collections.deque = collections.deque(maxlen=window)

    def update(self, dx: float, dy: float) -> tuple[float, float]:
        if len(self._dx_buf) >= 3:
            med_dx = float(np.median(self._dx_buf))
            med_dy = float(np.median(self._dy_buf))
            if abs(dx - med_dx) > self._spike_threshold:
                dx = med_dx
            if abs(dy - med_dy) > self._spike_threshold:
                dy = med_dy
        self._dx_buf.append(dx)
        self._dy_buf.append(dy)
        return float(np.median(self._dx_buf)), float(np.median(self._dy_buf))

    def reset(self) -> None:
        self._dx_buf.clear()
        self._dy_buf.clear()
