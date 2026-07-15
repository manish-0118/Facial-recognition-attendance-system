import sys
import os
import numpy as np
import cv2
from datetime import datetime

from core.database import mark_attendance, get_all_students, get_class_cutoffs, get_class_encodings
from core.logger import get_logger
from core.paths import data_dir, bundle_dir

_log = get_logger(__name__)

_DETECTOR_PATH    = os.path.join(bundle_dir(), 'models', 'face_detection_yunet_2023mar.onnx')
_RECOGNIZER_PATH  = os.path.join(bundle_dir(), 'models', 'face_recognition_sface_2021dec.onnx')
_EYE_CASCADE_PATH = os.path.join(bundle_dir(), 'cascades', 'haarcascade_eye.xml')
_STOP_SIGNAL      = os.path.join(data_dir(), 'stop_signal.txt')

# ── Liveness tuning ───────────────────────────────────────────────────────────
# A blink is: both eyes open for ≥ _EYE_OPEN_MIN frames, then 0 eyes for
# ≥ _EYE_CLOSED_MIN frames, then both eyes open again.
# A static photo cannot produce this sequence.
_EYE_OPEN_MIN    = 3   # consecutive frames with 2 eyes to establish baseline
_EYE_CLOSED_MIN  = 2   # consecutive frames with 0 eyes to register a blink
_BLINKS_REQUIRED = 1   # blinks needed to confirm liveness
_TRACK_MAX_DIST  = 80  # px — max center shift to count as the same face
_TRACK_MAX_AGE   = 10  # frames before an unmatched track is dropped


class _FaceTrack:
    """Tracks one face across frames and confirms liveness via blink detection."""

    __slots__ = ("cx", "cy", "open_streak", "closed_streak", "blink_count", "live", "age")

    def __init__(self, cx: int, cy: int) -> None:
        self.cx           = cx
        self.cy           = cy
        self.open_streak  = 0
        self.closed_streak = 0
        self.blink_count  = 0
        self.live         = False
        self.age          = 0

    def update(self, cx: int, cy: int, eye_count: int) -> None:
        self.cx  = cx
        self.cy  = cy
        self.age = 0

        if eye_count >= 2:
            # Eyes open — check if we just completed a valid blink
            if self.closed_streak >= _EYE_CLOSED_MIN and self.open_streak >= _EYE_OPEN_MIN:
                self.blink_count += 1
                if self.blink_count >= _BLINKS_REQUIRED:
                    self.live = True
            self.open_streak  += 1
            self.closed_streak = 0
        else:
            # Eyes not fully detected
            if self.open_streak >= _EYE_OPEN_MIN:
                # Only count as closing if we had a stable open baseline
                self.closed_streak += 1
            else:
                # No baseline yet — reset so we wait for a clean open state
                self.open_streak = 0


def _match_track(tracks: list, cx: int, cy: int):
    best, best_dist = None, _TRACK_MAX_DIST
    for t in tracks:
        d = ((cx - t.cx) ** 2 + (cy - t.cy) ** 2) ** 0.5
        if d < best_dist:
            best_dist = d
            best = t
    return best


def _parse_time(value):
    import datetime
    if isinstance(value, datetime.timedelta):
        total_seconds = int(value.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return datetime.time(hours, minutes)
    if isinstance(value, datetime.time):
        return value
    h, m = str(value).strip().split(":")[:2]
    return datetime.time(int(h), int(m))


def _resolve_status(now_time, late_cutoff, absent_cutoff):
    if now_time <= late_cutoff:
        return "present"
    if now_time <= absent_cutoff:
        return "late"
    return "absent"


def take_attendance_session(class_id):
    late_raw, absent_raw = get_class_cutoffs(class_id)
    late_raw   = late_raw   or '06:30'
    absent_raw = absent_raw or '07:00'
    late_cutoff   = _parse_time(late_raw)
    absent_cutoff = _parse_time(absent_raw)

    all_students = get_all_students()
    student_lookup = {
        str(row['student_id']): row['name']
        for row in all_students
        if int(row.get('class_id', -1)) == int(class_id)
    }

    known_embeddings, known_labels = get_class_encodings(class_id)
    if known_embeddings is None or len(known_embeddings) == 0:
        _log.error("take_attendance: no encodings in DB for class_id=%s", class_id)
        print(f"ERROR: No trained encodings found for class {class_id}. "
              "Register students and train the model first.", file=sys.stderr)
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        _log.error("take_attendance: could not open webcam for class_id=%s", class_id)
        print("ERROR: Could not open webcam", file=sys.stderr)
        return

    detector   = cv2.FaceDetectorYN.create(
        _DETECTOR_PATH, "", (640, 480),
        score_threshold=0.6, nms_threshold=0.3, top_k=5000,
    )
    recognizer = cv2.FaceRecognizerSF.create(_RECOGNIZER_PATH, "")

    eye_cascade = cv2.CascadeClassifier(_EYE_CASCADE_PATH)
    if eye_cascade.empty():
        _log.error("take_attendance: could not load eye cascade from %s", _EYE_CASCADE_PATH)
        print("ERROR: Could not load eye cascade classifier", file=sys.stderr)
        return

    marked: set  = set()
    tracks: list = []

    if os.path.exists(_STOP_SIGNAL):
        os.remove(_STOP_SIGNAL)

    try:
        while True:
            if os.path.exists(_STOP_SIGNAL):
                os.remove(_STOP_SIGNAL)
                break

            ret, frame = cap.read()
            if not ret:
                continue

            # Age all tracks each frame
            for t in tracks:
                t.age += 1

            gray     = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            now_time = datetime.now().time()
            _, faces = detector.detect(frame)

            cv2.putText(frame, f"Class: {class_id} | Marked: {len(marked)}",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            if faces is not None:
                for face in faces:
                    x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                    cx, cy = x + w // 2, y + h // 2

                    # ── Eye detection in upper 60% of face ROI ────────────
                    roi_top    = max(0, y)
                    roi_bottom = min(gray.shape[0], y + int(h * 0.6))
                    roi_left   = max(0, x)
                    roi_right  = min(gray.shape[1], x + w)
                    eye_roi    = gray[roi_top:roi_bottom, roi_left:roi_right]

                    eye_count = 0
                    if eye_roi.size > 0:
                        eyes = eye_cascade.detectMultiScale(
                            eye_roi,
                            scaleFactor=1.1,
                            minNeighbors=4,
                            minSize=(max(10, w // 8), max(10, h // 10)),
                            maxSize=(w // 2, h // 3),
                        )
                        eye_count = len(eyes)

                    # ── Match or create track, update blink state ─────────
                    track = _match_track(tracks, cx, cy)
                    if track is None:
                        track = _FaceTrack(cx, cy)
                        tracks.append(track)
                    track.update(cx, cy, eye_count)

                    # ── Liveness gate ─────────────────────────────────────
                    if not track.live:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 215, 255), 2)
                        cv2.putText(frame, "Blink to verify",
                                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, (0, 215, 255), 2)
                        continue

                    # ── Live — run recognition ────────────────────────────
                    try:
                        aligned = recognizer.alignCrop(frame, face)
                        query   = recognizer.feature(aligned).flatten()
                    except Exception:
                        continue

                    best_score = -1
                    best_label = "Unknown"
                    for emb, label in zip(known_embeddings, known_labels):
                        score = recognizer.match(
                            query.reshape(1, -1),
                            emb.reshape(1, -1),
                            cv2.FaceRecognizerSF_FR_COSINE,
                        )
                        if score > best_score:
                            best_score = score
                            best_label = label

                    if best_score >= 0.45:
                        sid          = best_label
                        display_name = student_lookup.get(sid, best_label)
                        confidence   = round(best_score * 100, 1)

                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        cv2.putText(frame, f"{display_name} {confidence}%",
                                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, (0, 255, 0), 2)

                        if sid not in marked:
                            status = _resolve_status(now_time, late_cutoff, absent_cutoff)
                            try:
                                inserted = mark_attendance(sid, display_name, class_id, status)
                                if inserted:
                                    marked.add(sid)
                            except Exception:
                                _log.exception("take_attendance: failed to mark attendance "
                                               "for sid=%s class_id=%s", sid, class_id)
                    else:
                        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown",
                                    (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, (0, 0, 255), 2)

            # Prune tracks not seen for too long
            tracks = [t for t in tracks if t.age <= _TRACK_MAX_AGE]

            cv2.putText(frame, "Press Q to stop",
                        (10, frame.shape[0] - 20), cv2.FONT_HERSHEY_SIMPLEX,
                        0.6, (200, 200, 200), 1)

            cv2.imshow("Take Attendance", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord('q'), ord('Q'), 27):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()


def main():
    if len(sys.argv) < 2:
        print("Usage: python take_attendance.py <class_id>")
        sys.exit(1)
    try:
        class_id = int(sys.argv[1])
    except Exception:
        print("class_id must be an integer")
        sys.exit(1)
    take_attendance_session(class_id)


if __name__ == '__main__':
    main()
