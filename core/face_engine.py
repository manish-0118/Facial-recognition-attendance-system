import os
import cv2
import numpy as np
import pickle
import shutil

# Model paths
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DETECTOR_PATH = os.path.join(_BASE, 'models', 'face_detection_yunet_2023mar.onnx')
_RECOGNIZER_PATH = os.path.join(_BASE, 'models', 'face_recognition_sface_2021dec.onnx')
_CASCADE_PATH = os.path.join(_BASE, 'cascades', 'haarcascade_frontalface_default.xml')


def _get_detector(width=640, height=480):
    detector = cv2.FaceDetectorYN.create(
        _DETECTOR_PATH, "", (width, height),
        score_threshold=0.6, nms_threshold=0.3, top_k=5000
    )
    return detector


def _get_recognizer():
    return cv2.FaceRecognizerSF.create(_RECOGNIZER_PATH, "")


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


def capture_face_images(student_id, name, class_id, count=50, progress_callback=None):
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

    face_cascade = cv2.CascadeClassifier(_CASCADE_PATH)

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        raise RuntimeError('Could not open webcam')

    saved = 0
    try:
        while saved < count:
            ret, frame = cap.read()
            if not ret:
                continue
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rects = face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
            )
            if len(rects) == 0:
                continue
            x, y, w, h = max(rects, key=lambda r: r[2] * r[3])
            pad = int(0.1 * max(w, h))
            fh_frame, fw_frame = frame.shape[:2]
            x1 = max(0, x - pad)
            y1 = max(0, y - pad)
            x2 = min(fw_frame, x + w + pad)
            y2 = min(fh_frame, y + h + pad)
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
            detector = _get_detector(w, h)
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
        raise RuntimeError('No face embeddings found to train for this class')

    data = {'embeddings': np.array(embeddings), 'labels': labels}
    with open(enc_path, 'wb') as f:
        pickle.dump(data, f)

    return len(student_folders), total_images


def recognize_face(face_aligned, class_id):
    enc_path = os.path.join(_BASE, 'trainer', f"{class_id}_encodings.pkl")
    if not os.path.exists(enc_path):
        return ("Unknown", 0)

    with open(enc_path, 'rb') as f:
        data = pickle.load(f)

    recognizer = _get_recognizer()
    embeddings = data.get('embeddings')
    labels = data.get('labels', [])

    if embeddings is None or len(embeddings) == 0:
        return ("Unknown", 0)

    query = recognizer.feature(face_aligned).flatten()
    best_score = -1
    best_label = "Unknown"

    for emb, label in zip(embeddings, labels):
        score = recognizer.match(
            query.reshape(1, -1),
            emb.reshape(1, -1),
            cv2.FaceRecognizerSF_FR_COSINE
        )
        if score > best_score:
            best_score = score
            best_label = label

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
            # ignore errors; caller shouldn't fail because cleanup failed
            continue

    return removed_any