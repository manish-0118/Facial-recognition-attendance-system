from __future__ import annotations

import queue
import threading
from pathlib import Path

import cv2
import dlib
import numpy as np

from database import log_action, mark_attendance
from gui import theme
from take_attendance import (
    CONFIDENCE_THRESHOLD,
    EYE_ASPECT_RATIO_THRESHOLD,
    FACE_SIZE,
    average_eye_aspect_ratio,
    build_label_map,
    load_students,
)


class CameraManager:
    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[np.ndarray, str, float, str]] = queue.Queue(maxsize=2)
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._running = False
        self._error: str | None = None
        self._source = 0
        self._admin_username = "system"

    def start(self, source: int = 0, admin_username: str | None = None) -> None:
        self._stop_event.clear()
        self._queue = queue.Queue(maxsize=2)
        self._source = source
        self._admin_username = admin_username or "system"
        self._error = None
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, name="attendance-camera", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        self._running = False

    def get_frame(self) -> tuple[np.ndarray, str, float, str] | None:
        latest_item: tuple[np.ndarray, str, float, str] | None = None
        while True:
            try:
                latest_item = self._queue.get_nowait()
            except queue.Empty:
                break
        return latest_item

    def is_running(self) -> bool:
        return self._running and not self._stop_event.is_set()

    def get_error(self) -> str | None:
        return self._error

    def _load_runtime(self) -> tuple[cv2.CascadeClassifier, object, dlib.shape_predictor, dict[int, tuple[str, str]]]:
        base_dir = Path(__file__).resolve().parent.parent
        cascade_path = base_dir / "cascades" / "haarcascade_frontalface_default.xml"
        model_path = base_dir / "trainer" / "trainer.yml"
        predictor_path = base_dir / "models" / "shape_predictor_68_face_landmarks.dat"
        dataset_dir = base_dir / "dataset"

        if not cascade_path.exists():
            raise FileNotFoundError(f"Haar cascade not found: {cascade_path}")
        if not model_path.exists():
            raise FileNotFoundError(f"Trained model not found: {model_path}")
        if not predictor_path.exists():
            raise FileNotFoundError(f"Dlib shape predictor not found: {predictor_path}")
        if not hasattr(cv2, "face") or not hasattr(cv2.face, "LBPHFaceRecognizer_create"):
            raise RuntimeError(
                "OpenCV LBPH face recognizer is unavailable. Install a build that includes cv2.face, such as opencv-contrib-python."
            )

        students = load_students()
        label_map = build_label_map(dataset_dir, students)
        face_cascade = cv2.CascadeClassifier(str(cascade_path))
        if face_cascade.empty():
            raise RuntimeError(f"Failed to load Haar cascade: {cascade_path}")

        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.read(str(model_path))
        shape_predictor = dlib.shape_predictor(str(predictor_path))
        return face_cascade, recognizer, shape_predictor, label_map

    def _push_result(self, item: tuple[np.ndarray, str, float, str]) -> None:
        while True:
            try:
                self._queue.put_nowait(item)
                return
            except queue.Full:
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    return

    def _capture_loop(self) -> None:
        cap: cv2.VideoCapture | None = None
        try:
            face_cascade, recognizer, shape_predictor, label_map = self._load_runtime()
            cap = cv2.VideoCapture(self._source)
            if not cap.isOpened():
                raise RuntimeError("Could not open the default webcam.")

            marked_present: set[str] = set()
            blink_detected: set[str] = set()
            eyes_closed: dict[str, bool] = {}

            while not self._stop_event.is_set():
                success, frame = cap.read()
                if not success:
                    raise RuntimeError("Failed to read a frame from the webcam.")

                grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    grayscale,
                    scaleFactor=1.2,
                    minNeighbors=5,
                    minSize=(80, 80),
                )

                result_name = ""
                result_confidence = 0.0
                result_blink_status = "No face detected"

                for x, y, width, height in faces:
                    face_region = grayscale[y : y + height, x : x + width]
                    normalized_face = cv2.resize(face_region, FACE_SIZE)
                    predicted_label, confidence = recognizer.predict(normalized_face)
                    is_match = confidence < CONFIDENCE_THRESHOLD and predicted_label in label_map

                    if is_match:
                        student_id, student_name = label_map[predicted_label]
                        display_text = f"{student_name} ({confidence:.1f})"
                        color = (0, 255, 0)
                        result_name = student_name
                        result_confidence = float(confidence)
                        result_blink_status = "Recognized"

                        if student_id not in marked_present:
                            dlib_face = dlib.rectangle(x, y, x + width, y + height)
                            landmarks = shape_predictor(grayscale, dlib_face)
                            average_ear = average_eye_aspect_ratio(landmarks)
                            eyes_are_closed = average_ear < EYE_ASPECT_RATIO_THRESHOLD

                            if eyes_are_closed and not eyes_closed.get(student_id, False):
                                blink_detected.add(student_id)

                            eyes_closed[student_id] = eyes_are_closed

                            if student_id in blink_detected:
                                attendance_marked = mark_attendance(student_id, student_name)
                                if attendance_marked:
                                    log_action(
                                        self._admin_username,
                                        "mark_attendance",
                                        f"Marked attendance for {student_name} ({student_id})",
                                    )
                                marked_present.add(student_id)
                                result_blink_status = "Attendance marked"
                            else:
                                display_text = "Please Blink to Verify"
                                result_blink_status = "Waiting for blink"
                    else:
                        display_text = f"Unknown ({confidence:.1f})"
                        color = (0, 0, 255)
                        result_name = "Unknown"
                        result_confidence = float(confidence)
                        result_blink_status = "Unknown face"

                    cv2.rectangle(frame, (x, y), (x + width, y + height), color, 2)
                    cv2.putText(
                        frame,
                        display_text,
                        (x, y - 10 if y > 20 else y + height + 25),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        color,
                        2,
                    )

                cv2.putText(
                    frame,
                    f"Present: {len(marked_present)}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    (0, 255, 0),
                    2,
                )

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._push_result((rgb_frame, result_name, result_confidence, result_blink_status))
        except Exception as error:
            self._error = str(error)
        finally:
            self._running = False
            self._stop_event.set()
            if cap is not None:
                cap.release()
            self._thread = None