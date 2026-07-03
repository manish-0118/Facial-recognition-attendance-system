import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler


def _resolve_log_dir() -> str:
    """Find the first writable directory for logs, from most preferred to least."""
    candidates = []

    if not getattr(sys, 'frozen', False):
        # Dev mode — prefer project-local logs/
        candidates.append(
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        )

    # Frozen or dev fallback — standard Windows user-writable locations
    appdata = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA") or ""
    localappdata = os.environ.get("LOCALAPPDATA") or ""
    home = os.path.expanduser("~")

    for base in filter(None, [appdata, localappdata, home]):
        candidates.append(os.path.join(base, "NihareekaAttendance", "logs"))

    # Last resort — temp dir (always writable)
    candidates.append(os.path.join(tempfile.gettempdir(), "NihareekaAttendance", "logs"))

    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".probe")
            with open(probe, "w") as f:
                f.write("")
            os.remove(probe)
            return path
        except (PermissionError, OSError):
            continue

    return tempfile.gettempdir()


_LOG_DIR = _resolve_log_dir()
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")

_FMT = logging.Formatter(
    "%(asctime)s  [%(levelname)-8s]  %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler: RotatingFileHandler | None = None


def _get_file_handler() -> RotatingFileHandler:
    global _file_handler
    if _file_handler is None:
        _file_handler = RotatingFileHandler(
            _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        _file_handler.setLevel(logging.DEBUG)
        _file_handler.setFormatter(_FMT)
    return _file_handler


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addHandler(_get_file_handler())

    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(_FMT)
    logger.addHandler(ch)

    logger.propagate = False
    return logger
