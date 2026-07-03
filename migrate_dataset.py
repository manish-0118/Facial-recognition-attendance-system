"""
One-time migration: read existing dataset/ folder into MariaDB student_images table,
then re-train each class so embeddings are stored in student_encodings.

Run once from the project root with the venv active:
    python migrate_dataset.py

Safe to re-run — existing DB images for a student are replaced, not duplicated.
After a successful migration you can delete the dataset/ folder.
"""
import os
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(BASE, 'dataset')


def main():
    # Ensure core layer can be imported
    sys.path.insert(0, BASE)

    try:
        from core.database import init_db, get_all_students, save_student_images
        from core.face_engine import train_class_model
    except ImportError as exc:
        print(f"Import error: {exc}")
        print("Make sure the venv is active and all dependencies are installed.")
        sys.exit(1)

    print("Initialising database connection...")
    try:
        init_db()
    except Exception as exc:
        print(f"Database init failed: {exc}")
        sys.exit(1)

    if not os.path.isdir(DATASET_DIR):
        print("No dataset/ directory found — nothing to migrate.")
        return

    # Build lookup: zfilled_prefix → actual student_id from DB
    students = get_all_students() or []
    sid_lookup: dict[str, str] = {}
    for s in students:
        sid = str(s['student_id'])
        sid_lookup[sid.zfill(3)] = sid   # "001" → "1" etc.
        sid_lookup[sid] = sid             # exact match

    classes_migrated: set[int] = set()
    total_images = 0

    for class_id_str in sorted(os.listdir(DATASET_DIR)):
        class_dir = os.path.join(DATASET_DIR, class_id_str)
        if not os.path.isdir(class_dir):
            continue
        try:
            class_id = int(class_id_str)
        except ValueError:
            print(f"  Skipping non-integer folder: {class_id_str}")
            continue

        print(f"\nClass {class_id}:")

        for student_folder in sorted(os.listdir(class_dir)):
            student_dir = os.path.join(class_dir, student_folder)
            if not os.path.isdir(student_dir):
                continue

            # Resolve student_id: folder format is "<zfilled_id>_<name>"
            prefix = student_folder.split('_')[0]
            student_id = sid_lookup.get(prefix) or sid_lookup.get(prefix.lstrip('0') or '0')

            if not student_id:
                print(f"  WARNING: could not match folder '{student_folder}' to a student in DB — skipping")
                continue

            image_bytes: list[bytes] = []
            for fname in sorted(os.listdir(student_dir)):
                if not fname.lower().endswith(('.jpg', '.jpeg', '.png')):
                    continue
                fpath = os.path.join(student_dir, fname)
                try:
                    with open(fpath, 'rb') as f:
                        image_bytes.append(f.read())
                except Exception as exc:
                    print(f"    Could not read {fpath}: {exc}")

            if not image_bytes:
                print(f"  {student_folder}: no images found — skipped")
                continue

            try:
                save_student_images(student_id, class_id, image_bytes)
                print(f"  {student_folder} (id={student_id}): {len(image_bytes)} images saved to DB")
                total_images += len(image_bytes)
                classes_migrated.add(class_id)
            except Exception as exc:
                print(f"  {student_folder}: DB write failed — {exc}")

    if not classes_migrated:
        print("\nNo images were migrated (dataset folders are empty or no matches found).")
        return

    print(f"\nMigrated {total_images} images across {len(classes_migrated)} class(es).")
    print("Training models from DB images...")

    for class_id in sorted(classes_migrated):
        try:
            n_students, n_images = train_class_model(class_id)
            print(f"  Class {class_id}: trained — {n_students} students, {n_images} embeddings")
        except Exception as exc:
            print(f"  Class {class_id}: training failed — {exc}")

    print("\nMigration complete.")
    print("You can now safely delete the dataset/ folder.")


if __name__ == '__main__':
    main()
