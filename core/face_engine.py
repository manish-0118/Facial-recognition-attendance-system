import os
import cv2 # pyright: ignore[reportMissingImports]
import numpy as np # pyright: ignore[reportMissingImports]
import pickle
import shutil

from core.logger import get_logger

_log = get_logger(__name__)

# Model paths
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DETECTOR_PATH = os.path.join(_BASE, 'models', 'face_detection_yunet_2023mar.onnx')
_RECOGNIZER_PATH = os.path.join(_BASE, 'models', 'face_recognition_sface_2021dec.onnx')
# Module-level model caches — loaded once, reused for the lifetime of the process
_detector_cache: dict[tuple[int, int], "cv2.FaceDetectorYN"] = {}
_recognizer: "cv2.FaceRecognizerSF | None" = None

# Embedding cache: {class_id: (file_mtime, embeddings_matrix, labels)}
_embedding_cache: dict[int, tuple[float, np.ndarray, list]] = {}


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



def detect_faces(frame):
    h, w = frame.shape[:2]
    detector = _get_detector(w, h)
    _, faces = detector.detect(frame)
    boxes = []
    if faces is None:
        return boxes
    for face in faces:
        x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
        boxes.append((x, y, fw, fh))
    return boxes


def _ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def capture_face_images(student_id, name, class_id, count=12, progress_callback=None):
    folder_name = f"{str(student_id).zfill(3)}_{name}"
    save_dir = os.path.join(_BASE, 'dataset', str(class_id), folder_name)
    _ensure_dir(save_dir)

    existing = [f for f in os.listdir(save_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    max_idx = 0
    for fn in existing:
        try:
            idx = int(os.path.splitext(fn)[0])
            if idx > max_idx:
                max_idx = idx
        except Exception:
            continue
    next_idx = max_idx + 1

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        _log.error("capture_face_images: webcam could not be opened for student_id=%s", student_id)
        raise RuntimeError('Could not open webcam')

    saved = 0
    try:
        while saved < count:
            ret, frame = cap.read()
            if not ret:
                continue
            fh_frame, fw_frame = frame.shape[:2]
            detector = _get_detector(fw_frame, fh_frame)
            _, faces = detector.detect(frame)
            if faces is None or len(faces) == 0:
                continue
            face = max(faces, key=lambda f: f[2] * f[3])
            x, y, fw, fh = int(face[0]), int(face[1]), int(face[2]), int(face[3])
            pad = int(0.1 * max(fw, fh))
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(fw_frame, x + fw + pad)
            y2 = min(fh_frame, y + fh + pad)
            face_img = frame[y1:y2, x1:x2]
            if face_img.size == 0:
                continue
            out_path = os.path.join(save_dir, f"{next_idx:04d}.jpg")
            cv2.imwrite(out_path, face_img)
            saved += 1
            next_idx += 1
            if progress_callback:
                try:
                    result = progress_callback(saved, count)
                    if result is False:
                        break
                except Exception:
                    pass
    finally:
        cap.release()

    return saved


def train_class_model(class_id):
    data_dir = os.path.join(_BASE, 'dataset', str(class_id))
    trainer_dir = os.path.join(_BASE, 'trainer')
    _ensure_dir(trainer_dir)
    enc_path = os.path.join(trainer_dir, f"{class_id}_encodings.pkl")

    if not os.path.exists(data_dir):
        _log.error("train_class_model: dataset directory not found: %s", data_dir)
        raise RuntimeError(f"Dataset directory not found: {data_dir}")

    recognizer = _get_recognizer()
    embeddings = []
    labels = []
    total_images = 0

    student_folders = [
        d for d in os.listdir(data_dir)
        if os.path.isdir(os.path.join(data_dir, d))
    ]

    for folder in student_folders:
        student_dir = os.path.join(data_dir, folder)
        image_files = [
            os.path.join(student_dir, f)
            for f in os.listdir(student_dir)
            if f.lower().endswith(('.png', '.jpg', '.jpeg'))
        ]
        for img_path in image_files:
            img = cv2.imread(img_path)
            if img is None:
                continue
            h, w = img.shape[:2]
            detector = _get_detector(w, h)  # cached per unique (w, h)
            _, faces = detector.detect(img)
            if faces is None or len(faces) == 0:
                continue
            face = faces[0]
            aligned = recognizer.alignCrop(img, face)
            embedding = recognizer.feature(aligned)
            embeddings.append(embedding.flatten())
            labels.append(folder)
            total_images += 1

    if len(embeddings) == 0:
        _log.error("train_class_model: no face embeddings found for class_id=%s", class_id)
        raise RuntimeError('No face embeddings found to train for this class')

    data = {'embeddings': np.array(embeddings), 'labels': labels}
    with open(enc_path, 'wb') as f:
        pickle.dump(data, f)

    # Drop stale cache so next recognition reads the freshly written file
    _embedding_cache.pop(class_id, None)

    return len(student_folders), total_images


def _load_embeddings(class_id: int) -> tuple:
    """Return (embeddings_matrix, labels), loading from disk only when the file changed."""
    enc_path = os.path.join(_BASE, 'trainer', f"{class_id}_encodings.pkl")
    if not os.path.exists(enc_path):
        return None, []

    try:
        mtime = os.path.getmtime(enc_path)
    except OSError:
        return None, []

    cached = _embedding_cache.get(class_id)
    if cached is not None and cached[0] == mtime:
        return cached[1], cached[2]

    try:
        with open(enc_path, 'rb') as f:
            data = pickle.load(f)
        emb = data.get('embeddings')
        lbl = data.get('labels', [])
        if emb is not None and len(emb) > 0:
            _embedding_cache[class_id] = (mtime, emb, lbl)
            return emb, lbl
    except Exception:
        _log.exception("_load_embeddings: failed to load encodings for class_id=%s from %s", class_id, enc_path)
    return None, []


def recognize_face(face_aligned, class_id):
    embeddings, labels = _load_embeddings(class_id)
    if embeddings is None or len(embeddings) == 0:
        return ("Unknown", 0)

    recognizer = _get_recognizer()
    query = recognizer.feature(face_aligned).flatten()

    # Vectorized cosine similarity — ~50-100× faster than per-row recognizer.match() loop
    query_norm = np.linalg.norm(query)
    if query_norm < 1e-8:
        return ("Unknown", 0)
    norms = np.linalg.norm(embeddings, axis=1)
    scores = (embeddings @ query) / (norms * query_norm + 1e-8)

    best_idx = int(np.argmax(scores))
    best_score = float(scores[best_idx])
    best_label = labels[best_idx]

    threshold = 0.363
    if best_score >= threshold:
        confidence = round(best_score * 100, 1)
        return (best_label, confidence)
    return ("Unknown", 0)


def get_model_status(class_id):
    enc_path = os.path.join(_BASE, 'trainer', f"{class_id}_encodings.pkl")
    return os.path.exists(enc_path)


def cleanup_student_dataset(student_id: str, class_id: int) -> bool:
    """Delete the dataset folder for a given student within a class.

    The folder name format used by capture_face_images is '<zfilled_id>_<name>'.
    Since the name may not be known here, match any folder starting with the
    zfilled student_id followed by an underscore, or the raw student_id.

    Returns True if a folder was removed, False otherwise.
    """
    data_dir = os.path.join(_BASE, 'dataset', str(class_id))
    if not os.path.exists(data_dir) or not os.path.isdir(data_dir):
        return False

    targets = []
    sid_z = str(student_id).zfill(3)
    for entry in os.listdir(data_dir):
        path = os.path.join(data_dir, entry)
        if not os.path.isdir(path):
            continue
        if entry.startswith(f"{sid_z}_") or entry.startswith(f"{student_id}_") or entry == str(student_id):
            targets.append(path)

    removed_any = False
    for tgt in targets:
        try:
            shutil.rmtree(tgt)
            removed_any = True
        except Exception:
            continue

    return removed_any
