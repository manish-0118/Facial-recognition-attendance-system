import logging
import os
from logging.handlers import RotatingFileHandler

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_LOG_DIR = os.path.join(_BASE, "logs")
os.makedirs(_LOG_DIR, exist_ok=True)

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
    """Return a module-level logger wired to logs/app.log (rotating, 5 MB × 3)."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    logger.addHandler(_get_file_handler())

    # Console: WARNING+ only so production stdout stays clean
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(_FMT)
    logger.addHandler(ch)

    logger.propagate = False
    return logger
