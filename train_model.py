import sys
from pathlib import Path

from core.face_engine import train_class_model


def _get_classes_from_dataset(dataset_dir: Path) -> list[str]:
    return sorted([path.name for path in dataset_dir.iterdir() if path.is_dir()])


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    dataset_dir = base_dir / "dataset"

    if not dataset_dir.exists() or not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset folder not found: {dataset_dir}")

    if len(sys.argv) > 1:
        class_ids = [sys.argv[1]]
        print(f"Training model for class: {class_ids[0]}")
    else:
        class_ids = _get_classes_from_dataset(dataset_dir)
        if not class_ids:
            print("No class folders found in dataset/. Nothing to train.")
            return
        print(f"Found {len(class_ids)} classes in dataset/. Starting training...")

    trained_classes = 0
    total_students = 0
    total_images = 0

    for class_id in class_ids:
        print(f"[TRAIN] Class {class_id}...")
        try:
            student_count, image_count = train_class_model(class_id)
            if image_count > 0:
                trained_classes += 1
                total_students += student_count
                total_images += image_count
                print(
                    f"[OK] Class {class_id}: {student_count} students, {image_count} images"
                )
            else:
                print(f"[SKIP] Class {class_id}: no usable images found")
        except Exception as err:
            print(f"[ERROR] Class {class_id}: {err}")

    print("\nTraining summary")
    print(f"Classes trained: {trained_classes}")
    print(f"Total students trained: {total_students}")
    print(f"Total images trained: {total_images}")


if __name__ == "__main__":
    main()