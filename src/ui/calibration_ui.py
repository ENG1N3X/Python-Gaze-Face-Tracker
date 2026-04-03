import tkinter as tk
import threading
import queue
import time
import pyautogui


class CalibrationUI:
    def __init__(self) -> None:
        self._screen_w, self._screen_h = pyautogui.size()
        self._cmd_queue = queue.Queue()
        self._ready_event = threading.Event()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready_event.wait()

    def _run(self) -> None:
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
        self._ready_event.set()
        while self._running:
            self._process_commands()
            self._root.update()
            time.sleep(0.016)
        self._root.destroy()

    def _process_commands(self) -> None:
        while not self._cmd_queue.empty():
            try:
                cmd = self._cmd_queue.get_nowait()
            except queue.Empty:
                break
            if cmd[0] == 'show_point':
                _, index, total, x, y = cmd
                self._canvas.delete('all')
                self._canvas.create_oval(
                    x - 20, y - 20, x + 20, y + 20,
                    fill='white', outline='white', tags='dot'
                )
                self._canvas.create_text(
                    x, y + 40,
                    text=f'Point {index + 1} of {total}',
                    fill='white', font=('Arial', 16), tags='label'
                )
                self._canvas.create_text(
                    x, y - 40,
                    text='Look at the dot...',
                    fill='gray', font=('Arial', 14), tags='hint'
                )
            elif cmd[0] == 'show_countdown':
                fraction = cmd[1]
                self._canvas.delete('countdown_arc')
                r = 30
                dot = self._canvas.coords('dot')
                if dot:
                    cx = (dot[0] + dot[2]) / 2
                    cy = (dot[1] + dot[3]) / 2
                    self._canvas.create_arc(
                        cx - r, cy - r, cx + r, cy + r,
                        start=90,
                        extent=fraction * 360,
                        style=tk.ARC,
                        outline='green',
                        width=4,
                        tags='countdown_arc',
                    )
            elif cmd[0] == 'close':
                self._running = False

    def show_point(self, index: int, total: int, x: int, y: int) -> None:
        self._cmd_queue.put(('show_point', index, total, x, y))

    def update_countdown(self, fraction: float) -> None:
        self._cmd_queue.put(('show_countdown', fraction))

    def close(self) -> None:
        self._cmd_queue.put(('close',))
        self._thread.join(timeout=2.0)
