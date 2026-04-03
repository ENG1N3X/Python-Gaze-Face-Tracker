import tkinter as tk
import pyautogui


class CalibrationUI:
    """Fullscreen calibration window.

    Must be created and used on the main thread (macOS NSWindow requirement).
    Call tick() each frame to keep the window responsive.
    """

    def __init__(self) -> None:
        self._screen_w, self._screen_h = pyautogui.size()
        self._root = tk.Tk()
        self._root.attributes('-fullscreen', True)
        self._root.attributes('-topmost', True)
        self._root.configure(bg='black')
        self._canvas = tk.Canvas(
            self._root,
            width=self._screen_w,
            height=self._screen_h,
            bg='black',
            highlightthickness=0,
        )
        self._canvas.pack(fill=tk.BOTH, expand=True)
        self._root.update()

    def tick(self) -> None:
        """Pump the tkinter event loop once — call every frame."""
        self._root.update()

    def show_point(self, index: int, total: int, x: int, y: int) -> None:
        self._canvas.delete('all')
        self._canvas.create_oval(
            x - 20, y - 20, x + 20, y + 20,
            fill='white', outline='white', tags='dot',
        )
        self._canvas.create_text(
            x, y + 40,
            text=f'Point {index + 1} of {total}',
            fill='white', font=('Arial', 16), tags='label',
        )
        self._canvas.create_text(
            x, y - 40,
            text='Look at the dot...',
            fill='gray', font=('Arial', 14), tags='hint',
        )
        self._root.update()

    def update_countdown(self, fraction: float) -> None:
        self._canvas.delete('countdown_arc')
        dot = self._canvas.coords('dot')
        if dot:
            cx = (dot[0] + dot[2]) / 2
            cy = (dot[1] + dot[3]) / 2
            r = 30
            self._canvas.create_arc(
                cx - r, cy - r, cx + r, cy + r,
                start=90,
                extent=fraction * 360,
                style=tk.ARC,
                outline='green',
                width=4,
                tags='countdown_arc',
            )
        self._root.update()

    def close(self) -> None:
        self._root.destroy()
