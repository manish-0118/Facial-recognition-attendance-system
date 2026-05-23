from pathlib import Path

import cv2


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    cascade_path = base_dir / "cascades" / "haarcascade_frontalface_default.xml"

    if not cascade_path.exists():
        raise FileNotFoundError(f"Haar cascade not found: {cascade_path}")

    face_cascade = cv2.CascadeClassifier(str(cascade_path))
    if face_cascade.empty():
        raise RuntimeError(f"Failed to load Haar cascade: {cascade_path}")

    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        raise RuntimeError("Could not open the default webcam.")

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break

            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = face_cascade.detectMultiScale(
                grayscale,
                scaleFactor=1.2,
                minNeighbors=5,
                minSize=(30, 30),
            )

            for x, y, width, height in faces:
                cv2.rectangle(frame, (x, y), (x + width, y + height), (0, 255, 0), 2)
                text_y = y - 10 if y - 10 > 20 else y + height + 25
                cv2.putText(
                    frame,
                    "Face Detected",
                    (x, text_y),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                )

            cv2.putText(
                frame,
                f"Face Count: {len(faces)}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 0),
                2,
            )

            cv2.imshow("Face Detection", frame)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()