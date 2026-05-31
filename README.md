# Biometric Attendance System

## Brief description
A desktop biometric attendance system that uses face detection and recognition to record student attendance. The GUI uses CustomTkinter; face detection uses OpenCV YuNet and face recognition uses SFace (ONNX). Attendance is stored in a MySQL database and can be exported to Excel/PDF.

## Requirements
- Python 3.11
- MySQL Server 9.x

### Python packages (exact versions)
The environment used for this project contains the following packages (output from `pip freeze`):

babel==2.18.0
charset-normalizer==3.4.7
colorama==0.4.6
contourpy==1.3.3
customtkinter==5.2.2
cycler==0.12.1
darkdetect==0.8.0
et_xmlfile==2.0.0
flatbuffers==25.12.19
fonttools==4.63.0
iniconfig==2.3.0
kiwisolver==1.5.0
matplotlib==3.10.9
mysql-connector-python==9.7.0
numpy==2.4.6
onnxruntime==1.26.0
opencv-contrib-python==4.13.0.92
openpyxl==3.1.5
packaging==26.2
pandas==3.0.3
pillow==12.2.0
pluggy==1.6.0
protobuf==7.35.0
Pygments==2.20.0
pyparsing==3.3.2
pytest==9.0.3
python-dateutil==2.9.0.post0
reportlab==4.5.1
six==1.17.0
tkcalendar==1.6.1
tzdata==2026.2

You can install them all with the following command (runs pip install with pinned versions):

pip install babel==2.18.0 charset-normalizer==3.4.7 colorama==0.4.6 contourpy==1.3.3 customtkinter==5.2.2 cycler==0.12.1 darkdetect==0.8.0 et_xmlfile==2.0.0 flatbuffers==25.12.19 fonttools==4.63.0 iniconfig==2.3.0 kiwisolver==1.5.0 matplotlib==3.10.9 mysql-connector-python==9.7.0 numpy==2.4.6 onnxruntime==1.26.0 opencv-contrib-python==4.13.0.92 openpyxl==3.1.5 packaging==26.2 pandas==3.0.3 pillow==12.2.0 pluggy==1.6.0 protobuf==7.35.0 Pygments==2.20.0 pyparsing==3.3.2 pytest==9.0.3 python-dateutil==2.9.0.post0 reportlab==4.5.1 six==1.17.0 tkcalendar==1.6.1 tzdata==2026.2

(Alternatively create a `requirements.txt` with the above lines and run `pip install -r requirements.txt`.)

## Setup Instructions
1. Clone the repo:

   git clone <your-repo-url>
   cd attendence_system_github

2. Create a virtual environment with Python 3.11 and activate it:

   python3.11 -m venv venv

   On Windows PowerShell:

   .\venv\Scripts\Activate.ps1

   On Windows CMD:

   .\venv\Scripts\activate.bat

3. Install required Python packages (see command above) or:

   pip install -r requirements.txt

4. MySQL setup

   - Start MySQL Server and create a database and user for the app. Example SQL (run in MySQL client):

     CREATE DATABASE attendance_system_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     CREATE USER 'attendance_user'@'localhost' IDENTIFIED BY 'change_me_password';
     GRANT ALL PRIVILEGES ON attendance_system_db.* TO 'attendance_user'@'localhost';
     FLUSH PRIVILEGES;

   - Note the credentials and update `config.ini` accordingly.

5. Create `config.ini` (project root) with this template:

   [database]
   host = localhost
   port = 3306
   user = attendance_user
   password = change_me_password
   database = attendance_system_db

   [models]
   models_dir = models
   cascades_dir = cascades

   [app]
   default_admin_username = superadmin
   default_admin_password = super123

6. Download required model files and place them in the specified folders:

   - face_detection_yunet_2023mar.onnx
     https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
     Save to: models/face_detection_yunet_2023mar.onnx

   - face_recognition_sface_2021dec.onnx
     https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx
     Save to: models/face_recognition_sface_2021dec.onnx

   - haarcascade_frontalface_default.xml
     https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml
     Save to: cascades/haarcascade_frontalface_default.xml

7. Run the GUI:

   python gui.py

## Database Setup Notes

MySQL is installed and runs locally on each machine. Your MySQL password never leaves your device.

Each person who sets up this project creates their own MySQL installation with their own root password. The `config.ini` file (which is gitignored) stores your local credentials and is never committed to the repository.

There are two separate passwords to be aware of:

- **MySQL password** — set during MySQL installation, controls access to the database server on your machine
- **App superadmin password (default: super123)** — controls access to the application itself, same for everyone on first run, should be changed after first login

The database tables are created automatically when you run `python gui.py` for the first time. No manual table creation is required beyond creating the database itself.

Each fresh installation starts with a completely empty database — no student data, attendance records or admins carry over between machines.

## Project Structure
- `core/` — backend helpers and database integration (`config.py`, `database.py`, `face_engine.py`, `scheduler.py`).
- `gui/` — CustomTkinter UI pages and app entry (`app.py`, `class_hub_page.py`, `register_page.py`, etc.).
- `models/` — ONNX model files for detection and recognition.
- `cascades/` — Haarcascade XML files.
- `dataset/` — captured face images organized per student/class.
- `trainer/` — model training utilities and scripts.
- `tests/` — unit tests.
- `venv_clean/` — a saved virtual environment (not for redistribution).
- `claude_planning/` — planning notes for Claude AI.

## Default Credentials
- Username: `superadmin`
- Password: `super123`

(Please change these after first login.)

## Tech Stack
- Python 3.11
- CustomTkinter (GUI)
- MySQL (database)
- OpenCV YuNet (face detection) + SFace (face recognition) via ONNX
- numpy, pandas, matplotlib, onnxruntime, opencv-contrib-python

---
If you want, I can also create a `requirements.txt` file with the pinned packages and optionally add a script to download the model files automatically.