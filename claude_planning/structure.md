Project: attendence_system_github

Top-level files and folders

- attendence_system.code-workspace
- config.ini
- database.py
- face_detect.py
- gui.py
- register_student.py
- take_attendance.py
- train_model.py
- cascades/
  - haarcascade_frontalface_default.xml
- core/
  - config.py
  - database.py
  - face_engine.py
  - scheduler.py
- dataset/
  - <class_id>/
    - <student_id>_<Student Name>/
- gui/
  - __init__.py
  - admin_page.py
  - app.py
  - archive_page.py
  - attendance_page.py
  - audit_page.py
  - camera_manager.py
  - class_hub_page.py
  - class_page.py
  - dashboard_page.py
  - export_page.py
  - login_page.py
  - notifications.py
  - records_page.py
  - register_page.py
  - settings_page.py
  - student_page.py
- models/
  - face_detection_yunet_2023mar.onnx
  - face_recognition_sface_2021dec.onnx
- tests/
  - test_register_page.py
- trainer/
- venv_clean/

Notes for Claude:
- `core/` contains backend helpers and DB integration.
- `gui/` contains the CustomTkinter-based UI pages.
- `dataset/` stores captured face images organized by class and student.
- `models/` holds ONNX models used for detection/recognition.
- `trainer/` is for model training utilities.
- `claude_planning/structure.md` (this file) summarizes the main structure for planning.

If you want, I can also generate an interactive tree listing, sample README, or empty placeholder files for missing modules.