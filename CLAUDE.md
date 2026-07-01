# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows desktop biometric attendance system for Nihareeka College of Management and Information Technology. CustomTkinter GUI, MySQL storage, and OpenCV face detection/recognition (YuNet + SFace via ONNX). Built for Python 3.11 on Windows.

## Commands

```powershell
# Activate the saved environment (Python 3.11)
.\venv_clean\Scripts\Activate.ps1

# Run the app (entry point — sets sys.path then launches gui.app.App)
python gui.py

# Run the attendance recognition session standalone (normally spawned as a subprocess by the GUI)
python take_attendance.py <class_id>

# Tests
pytest                              # all tests
pytest tests/test_register_page.py # single file
pytest tests/test_register_page.py::test_duplicate_student_id_prevents_capture  # single test
```

There is no lint/format tooling configured. There is no `requirements.txt`; exact pinned versions live in `README.md` (install with the `pip install ...` line there, or use `venv_clean/`).

## First-run requirements

- `config.ini` (project root, gitignored) — DB credentials + app cutoff times. `core/config.py` writes defaults on first run if missing. MySQL database must already exist; tables are auto-created by `core/database.py init_db()` at startup.
- Model files must be present (not committed): `models/face_detection_yunet_2023mar.onnx`, `models/face_recognition_sface_2021dec.onnx`, `cascades/haarcascade_frontalface_default.xml`. Download URLs are in `README.md`.
- Default app login: `superadmin` / `super123` (change after first login).

## Architecture

Three layers: `core/` (backend, no Tk imports), `gui/` (all UI), and root-level scripts (entry point + recognition subprocess).

### Core layer (`core/`)
- **`database.py`** — every DB call. `MySQLConnectionPool` (pool_size=5), `init_db()` creates schema. Tables: `admins`, `classes`, `students`, `attendance`, `audit_log`, `exports_log`, `system_config`. Admin passwords are hashed here. Student names are stored split into `first_name`/`middle_name`/`last_name`.
- **`face_engine.py`** — all CV/biometric logic: capture (Haar cascade), train (YuNet detect → SFace align+embed → per-class `trainer/<class_id>_encodings.pkl`), recognize (1-NN cosine similarity), `cleanup_student_dataset`. ONNX models and cascades are loaded once and cached at module level; embedding pickles cached by `(class_id, file_mtime)`. "Training" is embedding extraction only — the ONNX weights are frozen.
- **`config.py`** — `config.ini` read/write via `configparser`. `DEFAULTS` dict is the source of truth; parsed config is cached and invalidated on `update_config()`.
- **`scheduler.py`** — `AttendanceScheduler`, a daemon thread started in `app.py` that fires every 60s to auto-finalize attendance for classes past their end time. Uses `threading.Event.wait` so it wakes instantly on shutdown.
- **`logger.py`** / **`errors.py`** — shared logging (`get_logger(__name__)`) and error types.

### GUI layer (`gui/`)
- **`app.py`** — the shell: sidebar nav, session management (10-min idle → auto logout), toast notifications via `show_notification(message, kind)`, and the background scheduler thread. Roles are `admin` and `superadmin` (superadmin additionally sees Admin Management + Audit Log).
- **Page lifecycle:** all pages are built **once** at login and cached, stacked with `place(relwidth=1, relheight=1)`. Navigation (`show_page`) is a pure z-order change via `tkraise()` — no widget creation/destruction on page switch. Do not assume a page's `__init__` re-runs on navigation.
- **`theme.py`** — token-based theming. `ACTIVE_THEME` selects one of two full palettes (`dark_navy`, `light_slate`); all tokens are exported at module level, so any file does `from gui import theme; theme.ACCENT`. **New UI must use theme tokens**, not hardcoded colors.
- **`widgets.py`** — shared widgets including `AutoScrollFrame` (wraps every page for scrollability without breaking the stacking layout). The sidebar uses plain `tk.Frame`/`tk.Label` (not CTk) to avoid canvas hover-flicker.
- **`class_hub_page.py`** — the primary workflow, 3-level navigation: Level 0 class-list cards → Level 1 attendance/students toggle with date navigator → Level 2 student detail (filter bar + history table + profile card + export PDF/Excel + matplotlib chart). New features should follow this 3-level pattern.
- Other pages: `dashboard_page`, `register_page` (capture + train), `attendance_page`, `archive_page`, `export_page`, `settings_page`, `admin_page`, `audit_page`, `login_page`.
- **Likely legacy / not wired into `app.py`:** `class_page.py`, `records_page.py`, `student_page.py`, `camera_manager.py`, `notifications.py`. Verify imports before editing these.

### Recognition subprocess (`take_attendance.py`)
`attendance_page.py` launches `take_attendance.py <class_id>` as a separate `subprocess.Popen` (an OpenCV `cv2.imshow` window). It is **not** run in the GUI thread. Stop is signalled via a `stop_signal.txt` file at the project root: the GUI writes it, the loop deletes it and exits. The subprocess loads the class's `trainer/<class_id>_encodings.pkl`, matches with cosine similarity (threshold 0.45 in this file), and calls `mark_attendance`. Status is `present`/`late`/`absent` resolved against per-class cutoff times.

## Conventions & gotchas

- **Camera capture in the GUI** (registration) runs in a separate `CTkToplevel` with a threaded worker + frame queue for live preview — keep camera work off the Tk main thread.
- **Background DB work** uses `threading`; the audit log and attendance pages prefetch data on worker threads.
- **Soft delete:** students are archived via `soft_delete_student` → restore with `restore_student`; `hard_delete_student` is superadmin-only and requires password re-verification.
- **Attendance status colors** (`present=#57C46D`, `late=#F4C542`, `absent=#FF6B6B`) and the Level-2 matplotlib chart background are currently hardcoded alongside theme tokens — a known inconsistency, not the intended pattern.
- `config.ini`, `*.db`, `dataset/`, `*.log`, and model/encoding artifacts are gitignored. Don't commit credentials or captured face data.
