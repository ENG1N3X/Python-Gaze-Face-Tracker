# Mac Eye Control — Development Plan

**Date:** 2026-04-03
**Status:** In Progress

---

## Контекст

Существующий `main.py` — рабочий монолитный прототип с трекингом лица, определением моргания и оценкой позы головы. Все модули в `src/` созданы как пустые заглушки. Задача — реализовать их по очереди и переключить `main.py` на модульную архитектуру.

---

## Фазы разработки

### Фаза 0 — Рефакторинг: извлечение логики из `main.py` в модули

**Цель:** вынести уже работающий код в модули, чтобы иметь стабильную базу перед новыми фичами.

**Файлы для реализации:**

#### `src/utils/config.py`
- Функция `load_config(path) -> dict` — загружает `config/default_config.json`, мёрджит с пользовательским `config.json` если есть
- Функция `save_config(config, path)` — сохраняет конфиг

#### `src/utils/angle_buffer.py`
- Перенести логику из `AngleBuffer.py` (не изменяя оригинал)
- Класс `AngleBuffer(size)` с методами `add(angles)`, `get_average() -> list`

#### `src/tracking/face_mesh.py`
- Класс `FaceMeshTracker(config)`
- Метод `process(frame) -> (mesh_points_2d, mesh_points_3d) | None`
- Инкапсулирует `mp.solutions.face_mesh.FaceMesh`

#### `src/tracking/iris_tracker.py`
- Функция `get_iris_positions(mesh_points_2d) -> dict`
- Возвращает: `l_center`, `r_center`, `l_dx`, `l_dy`, `r_dx`, `r_dy`
- Константы индексов ирис/углов глаз вынести сюда

#### `src/tracking/blink_detector.py`
- Класс `BlinkDetector(config)`
- Метод `update(mesh_points_3d) -> bool` — возвращает True если зафиксировано моргание
- Хранит счётчик кадров, EAR порог из конфига

#### `src/tracking/head_pose.py`
- Класс `HeadPoseEstimator(config)`
- Метод `estimate(mesh_points, image_size) -> (pitch, yaw, roll)`
- Включает `normalize_pitch`, `AngleBuffer` для сглаживания
- Метод `recalibrate()` — сохранить текущие углы как нулевое положение

**Результат:** `main.py` переписывается тонким оркестратором, импортирующим модули. Поведение не меняется.

**Критерий готовности:** программа запускается и ведёт себя идентично текущему `main.py`.

---

### Фаза 1 — Калибровка (Gaze-to-Screen Mapping)

**Цель:** связать позицию ириса + позу головы с координатами экрана.

#### `src/ui/calibration_ui.py`
- Класс `CalibrationUI`
- Метод `show_point(index, total) -> (x, y)` — показывает точку на fullscreen tkinter окне
- Метод `show_countdown(seconds)` — анимация ожидания фиксации
- Метод `close()`
- Tkinter window должен быть поверх всех окон

#### `src/calibration/calibration.py`
- Класс `CalibrationSession(config)`
- Метод `run(tracker, iris_tracker, head_pose) -> CalibrationData`
- Логика: для каждой из 9 точек — показать точку, ждать `calibration_dwell_sec`, собрать `(iris_dx, iris_dy, pitch, yaw)` усреднённые за период, сохранить пару `(features, screen_xy)`
- Метод `save(path)` — сохранить в `data/calibration.json`
- Метод `load(path) -> CalibrationData | None`

#### `src/calibration/mapping.py`
- Класс `GazeMapper`
- Метод `fit(calibration_data)` — обучить модель (полиномиальная регрессия 2-го порядка через `numpy.polyfit` или sklearn, если доступен; иначе билинейная интерполяция)
- Метод `predict(iris_dx, iris_dy, pitch, yaw) -> (screen_x, screen_y)`
- Метод `is_calibrated() -> bool`

**Интеграция в `main.py`:**
- При старте: пробовать загрузить `data/calibration.json`
- Если нет — запустить `CalibrationSession.run()`
- Клавиша `R` в main loop — рекалибровка

**Критерий готовности:** после калибровки `GazeMapper.predict()` возвращает разумные координаты при тесте взглядом на разные углы экрана.

---

### Фаза 2 — Управление курсором

**Цель:** курсор следует за взглядом в реальном времени.

#### `src/control/cursor.py`
- Класс `CursorController(config)`
- Внутренний буфер сглаживания (EMA или `AngleBuffer` на `(x, y)`)
- Метод `move(screen_x, screen_y)` — вызывает `pyautogui.moveTo()` со сглаживанием
- Метод `set_enabled(bool)` — пауза/возобновление
- Параметр `smoothing_window` из конфига

**Интеграция в `main.py`:**
- Каждый кадр: `GazeMapper.predict()` → `CursorController.move()`
- Если лицо не обнаружено — курсор не двигается

**Критерий готовности:** курсор плавно следует за взглядом, нет резких прыжков.

---

### Фаза 3 — Клик двойным морганием

**Цель:** два моргания за 0.5с = левый клик мыши.

#### `src/control/clicker.py`
- Класс `DoubleBlinkClicker(config)`
- Метод `update(blink_detected: bool) -> bool` — возвращает True если сработал двойной клик
- Логика: запоминает timestamp последнего моргания, если два моргания в пределах `blink_double_interval_sec` — клик
- При срабатывании: `pyautogui.click()`
- Визуальный индикатор: возвращает флаг для отображения на экране

**Параметры из конфига:** `blink_double_interval_sec`

**Интеграция в `main.py`:**
- Каждый кадр: `BlinkDetector.update()` → `DoubleBlinkClicker.update()`
- Если клик сработал — нарисовать индикатор на кадре 0.3с

**Критерий готовности:** одиночные моргания не кликают, двойное моргание надёжно кликает.

---

### Фаза 4 — Прокрутка наклоном головы

**Цель:** наклон головы вперёд/назад = прокрутка.

#### `src/control/scroller.py`
- Класс `HeadTiltScroller(config)`
- Метод `update(pitch: float)` — вычисляет скорость и направление прокрутки
- Логика: если `pitch > scroll_threshold_pitch_up` → `pyautogui.scroll(+speed)`, если `pitch < scroll_threshold_pitch_down` → `pyautogui.scroll(-speed)`
- Скорость = линейная функция от превышения порога: `speed = base_speed * (|pitch| - threshold) / threshold`
- Нейтральная зона — нет прокрутки

**Параметры из конфига:** `scroll_threshold_pitch_up`, `scroll_threshold_pitch_down`, `scroll_speed`

**Критерий готовности:** прокрутка не срабатывает при нормальном положении головы, плавно активируется при наклоне.

---

### Фаза 5 — Конфиг и финальная полировка

**Цель:** все параметры в конфиге, удобное управление.

#### Горячие клавиши (в `main.py`)
| Клавиша | Действие |
|---|---|
| `P` | Пауза/возобновление управления курсором |
| `C` | Рекалибровка позы головы (нулевое положение) |
| `R` | Запуск полной перекалибровки взгляда |
| `Q` | Выход |

#### `config/default_config.json` — финальная версия
```json
{
  "camera_index": 0,
  "blink_threshold": 0.51,
  "blink_consec_frames": 2,
  "blink_double_interval_sec": 0.5,
  "scroll_threshold_pitch_up": 15,
  "scroll_threshold_pitch_down": -15,
  "scroll_speed": 5,
  "smoothing_window": 10,
  "calibration_dwell_sec": 1.0,
  "calibration_points": 9,
  "min_detection_confidence": 0.8,
  "min_tracking_confidence": 0.8
}
```

#### Вывод в консоль
- Убрать `print` каждый кадр
- Логировать только события: старт, калибровка, клик, ошибка

#### `main.py` — финальная структура
```python
config = load_config(...)
tracker = FaceMeshTracker(config)
iris = IrisTracker()
blink = BlinkDetector(config)
head_pose = HeadPoseEstimator(config)
mapper = GazeMapper()
cursor = CursorController(config)
clicker = DoubleBlinkClicker(config)
scroller = HeadTiltScroller(config)

# calibration load or run
# main loop: cap.read() → process → predict → move/click/scroll
```

**Критерий готовности:** приложение работает end-to-end, все параметры настраиваются через `config.json` без изменения кода.

---

## Порядок реализации

```
Фаза 0 → Фаза 1 → Фаза 2 → Фаза 3 → Фаза 4 → Фаза 5
```

Каждая фаза должна быть стабильной перед переходом к следующей.

---

## Зависимости (к установке)

Все уже в `requirements.txt` или стандартная библиотека:
- `mediapipe`, `opencv-python`, `numpy` — уже есть
- `pyautogui` — добавить если нет
- `tkinter` — встроен в Python
- `scikit-learn` — добавлен. Используется `Pipeline(PolynomialFeatures(degree=2) + Ridge(alpha=0.01))` для gaze mapping. Ridge регуляризация критична при 9 точках калибровки.

---

## Файлы которые НЕ трогаем

- `AngleBuffer.py` — legacy, только читаем
- Существующая структура `src/` — только заполняем пустые модули
