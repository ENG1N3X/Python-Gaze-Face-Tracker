import logging

import pyautogui

from src.control.snap_zones import SnapZoneRegistry

logger = logging.getLogger(__name__)


class CursorController:
    def __init__(self, config: dict) -> None:
        self._alpha_slow = config.get("smoothing_alpha", 0.08)
        self._alpha_fast = config.get("cursor_alpha_fast", 0.35)
        self._fast_threshold = config.get("cursor_fast_velocity_threshold_px", 80)
        self._deadzone = config.get("cursor_deadzone_px", 8)
        self._ema_x: float | None = None
        self._ema_y: float | None = None
        self._last_pos: tuple[int, int] | None = None
        self._enabled = True
        self._snap_zones = SnapZoneRegistry.from_config(config)
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0

    def move(self, screen_x: float, screen_y: float) -> tuple[int, int] | None:
        if not self._enabled:
            return None

        screen_w, screen_h = pyautogui.size()
        clamped_x = max(0, min(screen_x, screen_w - 1))
        clamped_y = max(0, min(screen_y, screen_h - 1))

        if self._ema_x is None:
            self._ema_x, self._ema_y = clamped_x, clamped_y
        else:
            velocity = ((clamped_x - self._ema_x) ** 2 + (clamped_y - self._ema_y) ** 2) ** 0.5
            alpha = self._alpha_fast if velocity > self._fast_threshold else self._alpha_slow
            self._ema_x = alpha * clamped_x + (1.0 - alpha) * self._ema_x
            self._ema_y = alpha * clamped_y + (1.0 - alpha) * self._ema_y

        new_x, new_y = int(self._ema_x), int(self._ema_y)

        if self._last_pos is not None:
            if abs(new_x - self._last_pos[0]) < self._deadzone and abs(new_y - self._last_pos[1]) < self._deadzone:
                return self._last_pos

        snapped = self._snap_zones.snap(new_x, new_y)
        if snapped is not None:
            new_x, new_y = int(snapped[0]), int(snapped[1])

        pyautogui.moveTo(new_x, new_y)
        self._last_pos = (new_x, new_y)
        return self._last_pos

    def reset_buffer(self) -> None:
        self._ema_x = None
        self._ema_y = None
        self._last_pos = None

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def is_enabled(self) -> bool:
        return self._enabled
