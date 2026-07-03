import sys
import os
import numpy as np
import cv2
from datetime import datetime

from core.database import mark_attendance, get_all_students, get_class_cutoffs, get_class_encodings
from core.logger import get_logger
from core.paths import data_dir, bundle_dir

_log = get_logger(__name__)

_DETECTOR_PATH = os.path.join(bundle_dir(), 'models', 'face_detection_yunet_2023mar.onnx')
_RECOGNIZER_PATH = os.path.join(bundle_dir(), 'models', 'face_recognition_sface_2021dec.onnx')
_STOP_SIGNAL = os.path.join(data_dir(), 'stop_signal.txt')


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
    late_raw = late_raw or '06:30'
    absent_raw = absent_raw or '07:00'
    late_cutoff = _parse_time(late_raw)
    absent_cutoff = _parse_time(absent_raw)

    all_students = get_all_students()
    student_lookup = {
        str(row['student_id']): row['name']
        for row in all_students
        if int(row.get('class_id', -1)) == int(class_id)
    }

    # Load embeddings from database instead of pkl file
    known_embeddings, known_labels = get_class_encodings(class_id)
    if known_embeddings is None or len(known_embeddings) == 0:
        _log.error("take_attendance: no encodings in DB for class_id=%s", class_id)
        print(f"ERROR: No trained encodings found for class {class_id}. "
              "Register students and train the model first.", file=sys.stderr)
        return

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)

    if not cap.isOpened():
        _log.error("take_attendance: could not open webcam for class_id=%s", class_id)
        print("ERROR: Could not open webcam", file=sys.stderr)
        return

    detector = cv2.FaceDetectorYN.create(
        _DETECTOR_PATH, "", (640, 480),
        score_threshold=0.6, nms_threshold=0.3, top_k=5000
    )
    recognizer = cv2.FaceRecognizerSF.create(_RECOGNIZER_PATH, "")

    marked = set()
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

            now_time = datetime.now().time()
            _, faces = detector.detect(frame)

            cv2.putText(frame, f"Class: {class_id} | Marked: {len(marked)}",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

            if faces is not None:
                for face in faces:
                    x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])

                    try:
                        aligned = recognizer.alignCrop(frame, face)
                        query = recognizer.feature(aligned).flatten()
                    except Exception:
                        continue

                    best_score = -1
                    best_label = "Unknown"

                    for emb, label in zip(known_embeddings, known_labels):
                        score = recognizer.match(
                            query.reshape(1, -1),
                            emb.reshape(1, -1),
                            cv2.FaceRecognizerSF_FR_COSINE
                        )
                        if score > best_score:
                            best_score = score
                            best_label = label

                    if best_score >= 0.45:
                        sid = best_label
                        display_name = student_lookup.get(sid, best_label)
                        confidence = round(best_score * 100, 1)

                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                        cv2.putText(frame, f"{display_name} {confidence}%",
                                   (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

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
                        cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 0, 255), 2)
                        cv2.putText(frame, "Unknown",
                                   (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.putText(frame, "Press Q to stop",
                       (10, frame.shape[0]-20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

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
