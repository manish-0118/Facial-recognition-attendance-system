import os
import sys


def app_dir() -> str:
    """Exe directory — used only for locating bundled binaries (mariadb/).
    Do NOT use for writable files — Program Files is read-only at runtime."""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_dir() -> str:
    """Writable persistent data directory, always writable by the current user.
    Frozen: C:\\Users\\<user>\\AppData\\Roaming\\NihareekaAttendance
    Dev:    project root"""
    if getattr(sys, 'frozen', False):
        base = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
        path = os.path.join(base, "NihareekaAttendance")
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def bundle_dir() -> str:
    """Read-only bundled assets — _internal/ when frozen, project root in dev.
    Use for models/, cascades/, assets/."""
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
