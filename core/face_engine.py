import os
import cv2
import numpy as np

from core.logger import get_logger
from core.paths import bundle_dir
from core.database import (
    get_all_images_for_class,
    save_class_encodings,
    get_class_encodings,
    delete_student_images,
    delete_student_encodings,
    has_class_encodings,
)

_log = get_logger(__name__)

_DETECTOR_PATH = os.path.join(bundle_dir(), 'models', 'face_detection_yunet_2023mar.onnx')
_RECOGNIZER_PATH = os.path.join(bundle_dir(), 'models', 'face_recognition_sface_2021dec.onnx')

_detector_cache: dict = {}
_recognizer = None

# {class_id: (embeddings_matrix, labels)} — invalidated after training
_embedding_cache: dict = {}


def _get_detector(width: int = 640, height: int = 480):
    key = (width, height)
    if key not in _detector_cache:
        _detector_cache[key] = cv2.FaceDetectorYN.create(
            _DETECTOR_PATH, "", (width, height),
            score_threshold=0.6, nms_threshold=0.3, top_k=5000
        )
    return _detector_cache[key]


def _get_recognizer():
    global _recognizer
    if _recognizer is None:
        _recognizer = cv2.FaceRecognizerSF.create(_RECOGNIZER_PATH, "")
    return _recognizer


def train_class_model(class_id: int) -> tuple:
    """
    Load all face images for a class from the database, compute SFace embeddings,
    and store them back in the database. No filesystem access — uses cv2.imdecode.
    Returns (unique_students, total_images_trained).
    """
    image_rows = get_all_images_for_class(class_id)
    if not image_rows:
        _log.error("train_class_model: no images found in DB for class_id=%s", class_id)
        raise RuntimeError("No face images found in the database for this class. "
                           "Register students before training.")

    recognizer = _get_recognizer()
    embeddings = []
    labels = []

    for student_id, img_bytes in image_rows:
        img_arr = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        detector = _get_detector(w, h)
        _, faces = detector.detect(img)
        if faces is None or len(faces) == 0:
            continue
        face = faces[0]
        try:
            aligned = recognizer.alignCrop(img, face)
            embedding = recognizer.feature(aligned).flatten()
            embeddings.append(embedding)
            labels.append(str(student_id))
        except Exception:
            _log.exception("train_class_model: failed to compute embedding for student_id=%s", student_id)
            continue

    if not embeddings:
        _log.error("train_class_model: no embeddings extracted for class_id=%s", class_id)
        raise RuntimeError("No face embeddings could be extracted. "
                           "Ensure students have clear face photos captured.")

    save_class_encodings(class_id, labels, embeddings)
    _embedding_cache.pop(class_id, None)

    unique_students = len(set(labels))
    _log.info("train_class_model: class_id=%s trained — %d students, %d embeddings",
              class_id, unique_students, len(embeddings))
    return unique_students, len(embeddings)


def _load_embeddings(class_id: int) -> tuple:
    """Return (embeddings_matrix, labels), loading from DB only when not cached."""
    if class_id in _embedding_cache:
        return _embedding_cache[class_id]

    emb, lbl = get_class_encodings(class_id)
    if emb is not None and len(emb) > 0:
        _embedding_cache[class_id] = (emb, lbl)
        return emb, lbl

    return None, []


def get_model_status(class_id: int) -> bool:
    """Return True if trained embeddings exist in the database for this class."""
    return has_class_encodings(class_id)


def cleanup_student_dataset(student_id: str, class_id: int) -> bool:
    """Delete all face images and encodings for a student from the database."""
    try:
        delete_student_images(str(student_id), class_id)
        delete_student_encodings(str(student_id), class_id)
        _embedding_cache.pop(class_id, None)
        return True
    except Exception:
        _log.exception("cleanup_student_dataset: failed for student_id=%s class_id=%s",
                       student_id, class_id)
        return False
