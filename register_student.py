import re
from pathlib import Path

import cv2

from database import add_student, log_action


TARGET_IMAGE_COUNT = 50


def sanitize_name(name: str) -> str:
    cleaned_name = re.sub(r"\s+", "_", name.strip())
    return re.sub(r"[^A-Za-z0-9_-]", "", cleaned_name)


def prompt_non_empty(prompt: str) -> str:
    value = input(prompt).strip()
    if not value:
        raise ValueError("Student name and ID must not be empty.")
    return value


def get_next_image_number(dataset_dir: Path, student_id: str) -> int:
    existing_indices: list[int] = []

    for image_path in dataset_dir.glob(f"{student_id}_*.jpg"):
        suffix = image_path.stem.rsplit("_", 1)[-1]
        if suffix.isdigit():
            existing_indices.append(int(suffix))

    if not existing_indices:
        return 1

    return max(existing_indices) + 1


def register_student_capture(student_name: str, student_id: str, registered_by: str) -> Path:
    safe_name = sanitize_name(student_name)
    if not safe_name:
        raise ValueError("Student name must contain letters, numbers, spaces, hyphens, or underscores.")

    student_id = student_id.strip()
    registered_by = registered_by.strip()
    if not student_id:
        raise ValueError("Student ID must not be empty.")
    if not registered_by:
        raise ValueError("Registered-by admin username must not be empty.")

    base_dir = Path(__file__).resolve().parent
    cascade_path = base_dir / "cascades" / "haarcascade_frontalface_default.xml"
    dataset_dir = base_dir / "dataset" / f"{student_id}_{safe_name}"

    if not cascade_path.exists():
        raise FileNotFoundError(f"Haar cascade not found: {cascade_path}")

    dataset_dir.mkdir(parents=True, exist_ok=True)
    next_image_number = get_next_image_number(dataset_dir, student_id)

    face_cascade = cv2.CascadeClassifier(str(cascade_path))
    if face_cascade.empty():
        raise RuntimeError(f"Failed to load Haar cascade: {cascade_path}")

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not open the default webcam.")

    captured_images = 0

    try:
        while captured_images < TARGET_IMAGE_COUNT:
            success, frame = camera.read()
            if not success:
                raise RuntimeError("Failed to read a frame from the webcam.")

            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                grayscale,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(80, 80),
            )

            if len(faces) > 0:
                x, y, width, height = max(faces, key=lambda face: face[2] * face[3])
                face_region = grayscale[y : y + height, x : x + width]

                captured_images += 1
                image_number = next_image_number + captured_images - 1
                image_path = dataset_dir / f"{student_id}_{image_number:02d}.jpg"
                cv2.imwrite(str(image_path), face_region)

                cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
                cv2.putText(
                    frame,
                    "Capturing Face",
                    (x, y - 10 if y > 20 else y + height + 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

            cv2.putText(
                frame,
                f"Captured: {captured_images}/{TARGET_IMAGE_COUNT}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Register Student", frame)
            cv2.waitKey(1)
    finally:
        camera.release()
        cv2.destroyAllWindows()

    add_student(student_id, student_name, registered_by)
    log_action(registered_by, "register_student", f"Registered student {student_name} ({student_id})")
    print(f"Saved {captured_images} face images to {dataset_dir}")
    print("Student record saved to attendance_system.db")
    return dataset_dir


def main() -> None:
    registered_by = prompt_non_empty("Enter admin username: ")
    student_name = prompt_non_empty("Enter student name: ")
    student_id = prompt_non_empty("Enter student ID: ")
    register_student_capture(student_name, student_id, registered_by)


if __name__ == "__main__":
    main()