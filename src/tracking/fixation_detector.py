class GazeFixationDetector:
    """Detects when the user fixates on a point by counting consecutive stable frames.

    Each call to update() checks frame-to-frame iris movement. If movement
    exceeds movement_threshold, the stable-frame counter is fully reset.
    Fixation is confirmed only after window_frames consecutive stable frames.

    This is more reliable than std-based detection because:
    - Any gaze shift immediately resets progress (no "averaging away" bad frames)
    - Integer iris coordinates don't cause false positives via quantization
    """

    def __init__(self, config: dict) -> None:
        self._window = config.get("fixation_window_frames", 20)
        # Max allowed frame-to-frame iris movement (pixels) before reset
        self._movement_threshold = config.get("fixation_movement_threshold", 2.5)
        self._stable_frames: int = 0
        self._prev_dx: float | None = None
        self._prev_dy: float | None = None

    def update(self, iris_dx: float, iris_dy: float) -> None:
        if self._prev_dx is not None:
            delta = abs(iris_dx - self._prev_dx) + abs(iris_dy - self._prev_dy)
            if delta > self._movement_threshold:
                self._stable_frames = 0  # gaze moved — full reset
            else:
                self._stable_frames += 1
        else:
            self._stable_frames = 0

        self._prev_dx = iris_dx
        self._prev_dy = iris_dy

    def is_fixated(self) -> bool:
        return self._stable_frames >= self._window

    def progress(self) -> float:
        """0.0–1.0: fraction of required stable frames accumulated."""
        return min(1.0, self._stable_frames / self._window)

    def reset(self) -> None:
        self._stable_frames = 0
        self._prev_dx = None
        self._prev_dy = None
