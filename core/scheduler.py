from __future__ import annotations

import threading
import time
from datetime import date, datetime
from typing import Optional

from core.database import (
    get_all_classes_with_times,
    is_attendance_finalized,
    finalize_attendance,
)
from core.database import get_system_config
from datetime import time as _time
from datetime import datetime as _dt


def _parse_time(val) -> _time | None:
    if val is None:
        return None
    # if it's already a time-like object
    try:
        if hasattr(val, "hour") and hasattr(val, "minute"):
            return val
    except Exception:
        pass
    # string parse formats
    try:
        s = str(val).strip()
        if not s:
            return None
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return _dt.strptime(s, fmt).time()
            except Exception:
                continue
    except Exception:
        return None
    return None


class AttendanceScheduler:
    def __init__(self, interval_seconds: int = 60) -> None:
        self._interval = interval_seconds
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                classes = get_all_classes_with_times() or []
                today = date.today()
                now_time = datetime.now().time()
                for c in classes:
                    try:
                        cid = int(c.get("id"))
                        # prefer effective_end_time (may already include fallback), else use class_end_time
                        eff = c.get("effective_end_time") if c.get("effective_end_time") is not None else c.get("class_end_time")
                        comp_time = _parse_time(eff)
                        if comp_time is None:
                            # fallback to global absent_cutoff
                            abs_cfg = get_system_config("absent_cutoff")
                            comp_time = _parse_time(abs_cfg)
                        if comp_time is None:
                            continue
                        if now_time >= comp_time and not is_attendance_finalized(cid, today):
                            try:
                                finalize_attendance(cid, today)
                            except Exception:
                                # swallow per-class errors
                                pass
                    except Exception:
                        continue
            except Exception:
                pass
            # wait
            for _ in range(int(self._interval)):
                if self._stop_event.is_set():
                    break
                time.sleep(1)
