# Mac Eye Control — Distribution Plan (Non-Technical Users)

**Date:** 2026-04-03
**Status:** Planned (implement after Phase 5 is stable)

---

## Цель

Сделать приложение доступным для пользователей без знания программирования — скачал, запустил, откалибровал, пользуешься.

---

## Выбранный подход: py2app → .app bundle → DMG

### Шаг 1 — Сборка `.app` через `py2app`

```bash
pip install py2app
python setup.py py2app
```

Упаковывает Python + все зависимости (MediaPipe, OpenCV, scikit-learn и др.) в единый `.app` bundle.

- Размер: ~200–400 MB (из-за MediaPipe + OpenCV)
- Использовать `--alias` режим при разработке, финальная сборка — `--standalone`

### Шаг 2 — DMG-инсталлятор

Обернуть `.app` в `.dmg` — стандартный формат установки для macOS. Пользователь перетаскивает иконку в `/Applications`.

Инструмент: `create-dmg` (brew install create-dmg).

### Альтернатива — PyInstaller

Если `py2app` даёт проблемы с MediaPipe:
```bash
pip install pyinstaller
pyinstaller --onedir main.py
```

---

## Нетехнические барьеры и решения

| Барьер | Решение |
|---|---|
| Разрешение Accessibility (pyautogui) | Диалог при первом запуске с инструкцией и кнопкой открыть настройки |
| Разрешение камеры | macOS запросит автоматически при первом доступе |
| Калибровка | Обязательный fullscreen wizard при первом запуске (уже в Фазе 1) |
| Настройка параметров | В будущем — простой GUI вместо редактирования JSON |
| Подпись приложения | Apple Developer ID ($99/год) для обхода Gatekeeper; без подписи — инструкция как открыть через правый клик |

---

## Что важно учесть при разработке (прямо сейчас)

- Не хардкодить абсолютные пути — использовать пути относительно `__file__` или `sys._MEIPASS`
- Не требовать терминала для запуска и настройки
- `data/calibration.json` и `config.json` хранить в `~/Library/Application Support/MacEyeControl/`
- Логи — туда же, не в папку приложения (она может быть read-only после установки)

---

## Порядок реализации

1. Phases 0–5 — рабочее приложение
2. Перенос путей хранения данных в `~/Library/Application Support/`
3. Экран приветствия с проверкой Accessibility разрешения
4. Сборка `.app` через `py2app`
5. Упаковка в `.dmg`
6. Тест на чистой macOS без Python

---

## Зависимости для сборки (не для запуска)

```
py2app
create-dmg  # через brew
```
