import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path


DATABASE_PATH = Path(__file__).resolve().parent / "attendance_system.db"
DEFAULT_SUPERADMIN_USERNAME = "superadmin"
DEFAULT_SUPERADMIN_PASSWORD = "super123"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
DATE_FORMAT = "%Y-%m-%d"
TIME_FORMAT = "%H:%M:%S"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DATABASE_PATH)


def _current_timestamp() -> str:
    return datetime.now().strftime(TIMESTAMP_FORMAT)


def _current_date() -> str:
    return datetime.now().strftime(DATE_FORMAT)


def _current_time() -> str:
    return datetime.now().strftime(TIME_FORMAT)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _get_table_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    cursor = connection.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def _ensure_columns(connection: sqlite3.Connection, table_name: str, columns: dict[str, str]) -> None:
    existing_columns = _get_table_columns(connection, table_name)
    cursor = connection.cursor()
    for column_name, column_definition in columns.items():
        if column_name not in existing_columns:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def _ensure_default_superadmin(connection: sqlite3.Connection) -> None:
    cursor = connection.cursor()
    password_hash = _hash_password(DEFAULT_SUPERADMIN_PASSWORD)

    cursor.execute("SELECT id FROM admins WHERE role = 'superadmin' LIMIT 1")
    existing_superadmin = cursor.fetchone()
    if existing_superadmin is not None:
        return

    cursor.execute("SELECT id FROM admins WHERE username = ? LIMIT 1", (DEFAULT_SUPERADMIN_USERNAME,))
    existing_username = cursor.fetchone()
    created_date = _current_timestamp()

    if existing_username is not None:
        cursor.execute(
            """
            UPDATE admins
            SET password_hash = ?, role = 'superadmin', created_by = ?, created_date = ?
            WHERE username = ?
            """,
            (password_hash, "system", created_date, DEFAULT_SUPERADMIN_USERNAME),
        )
        return

    cursor.execute(
        """
        INSERT INTO admins (username, password_hash, role, created_by, created_date)
        VALUES (?, ?, 'superadmin', ?, ?)
        """,
        (DEFAULT_SUPERADMIN_USERNAME, password_hash, "system", created_date),
    )


def init_db() -> None:
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT,
                name TEXT NOT NULL,
                registered_date TEXT NOT NULL,
                registered_by TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS students_archive (
                id INTEGER PRIMARY KEY,
                student_id TEXT,
                name TEXT NOT NULL,
                registered_date TEXT NOT NULL,
                registered_by TEXT NOT NULL,
                deleted_by TEXT NOT NULL,
                deleted_date TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                name TEXT NOT NULL,
                date TEXT NOT NULL,
                time TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('superadmin', 'admin')),
                created_by TEXT NOT NULL,
                created_date TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS admins_archive (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_date TEXT NOT NULL,
                deleted_by TEXT NOT NULL,
                deleted_date TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS exports_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_username TEXT NOT NULL,
                export_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
            """
        )

        _ensure_columns(
            connection,
            "students",
            {
                "student_id": "TEXT",
                "name": "TEXT NOT NULL DEFAULT ''",
                "registered_date": "TEXT NOT NULL DEFAULT ''",
                "registered_by": "TEXT NOT NULL DEFAULT 'system'",
            },
        )
        _ensure_columns(
            connection,
            "students_archive",
            {
                "student_id": "TEXT",
                "name": "TEXT NOT NULL DEFAULT ''",
                "registered_date": "TEXT NOT NULL DEFAULT ''",
                "registered_by": "TEXT NOT NULL DEFAULT 'system'",
                "deleted_by": "TEXT NOT NULL DEFAULT 'system'",
                "deleted_date": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _ensure_columns(
            connection,
            "attendance",
            {
                "student_id": "TEXT NOT NULL DEFAULT ''",
                "name": "TEXT NOT NULL DEFAULT ''",
                "date": "TEXT NOT NULL DEFAULT ''",
                "time": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _ensure_columns(
            connection,
            "admins",
            {
                "username": "TEXT NOT NULL DEFAULT ''",
                "password_hash": "TEXT NOT NULL DEFAULT ''",
                "role": "TEXT NOT NULL DEFAULT 'admin'",
                "created_by": "TEXT NOT NULL DEFAULT 'system'",
                "created_date": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _ensure_columns(
            connection,
            "admins_archive",
            {
                "username": "TEXT NOT NULL DEFAULT ''",
                "password_hash": "TEXT NOT NULL DEFAULT ''",
                "role": "TEXT NOT NULL DEFAULT 'admin'",
                "created_by": "TEXT NOT NULL DEFAULT 'system'",
                "created_date": "TEXT NOT NULL DEFAULT ''",
                "deleted_by": "TEXT NOT NULL DEFAULT 'system'",
                "deleted_date": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _ensure_columns(
            connection,
            "audit_log",
            {
                "admin_username": "TEXT NOT NULL DEFAULT ''",
                "action": "TEXT NOT NULL DEFAULT ''",
                "details": "TEXT NOT NULL DEFAULT ''",
                "timestamp": "TEXT NOT NULL DEFAULT ''",
            },
        )
        _ensure_columns(
            connection,
            "exports_log",
            {
                "admin_username": "TEXT NOT NULL DEFAULT ''",
                "export_type": "TEXT NOT NULL DEFAULT ''",
                "filename": "TEXT NOT NULL DEFAULT ''",
                "timestamp": "TEXT NOT NULL DEFAULT ''",
            },
        )

        _ensure_default_superadmin(connection)
        connection.commit()


def add_student(student_id: str, name: str, registered_by: str) -> None:
    init_db()
    student_id = student_id.strip()
    name = name.strip()
    registered_by = registered_by.strip()

    if not student_id or not name or not registered_by:
        raise ValueError("student_id, name, and registered_by are required.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM students WHERE student_id = ? LIMIT 1", (student_id,))
        if cursor.fetchone() is not None:
            raise ValueError(f"Student ID already exists: {student_id}")

        cursor.execute(
            """
            INSERT INTO students (student_id, name, registered_date, registered_by)
            VALUES (?, ?, ?, ?)
            """,
            (student_id, name, _current_timestamp(), registered_by),
        )
        connection.commit()


def soft_delete_student(student_id: str, deleted_by: str) -> bool:
    init_db()
    student_id = student_id.strip()
    deleted_by = deleted_by.strip()

    if not student_id or not deleted_by:
        raise ValueError("student_id and deleted_by are required.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, student_id, name, registered_date, registered_by
            FROM students
            WHERE student_id = ?
            LIMIT 1
            """,
            (student_id,),
        )
        student_row = cursor.fetchone()
        if student_row is None:
            return False

        cursor.execute(
            "DELETE FROM students_archive WHERE student_id = ?",
            (student_id,),
        )
        cursor.execute(
            """
            INSERT INTO students_archive (
                id, student_id, name, registered_date, registered_by, deleted_by, deleted_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (*student_row, deleted_by, _current_timestamp()),
        )
        cursor.execute("DELETE FROM students WHERE student_id = ?", (student_id,))
        connection.commit()
        return True


def hard_delete_student(student_id: str) -> bool:
    init_db()
    student_id = student_id.strip()
    if not student_id:
        raise ValueError("student_id is required.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM students_archive WHERE student_id = ?", (student_id,))
        deleted = cursor.rowcount > 0
        connection.commit()
        return deleted


def restore_student(student_id: str) -> bool:
    init_db()
    student_id = student_id.strip()
    if not student_id:
        raise ValueError("student_id is required.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM students WHERE student_id = ? LIMIT 1", (student_id,))
        if cursor.fetchone() is not None:
            return False

        cursor.execute(
            """
            SELECT id, student_id, name, registered_date, registered_by
            FROM students_archive
            WHERE student_id = ?
            LIMIT 1
            """,
            (student_id,),
        )
        archive_row = cursor.fetchone()
        if archive_row is None:
            return False

        _, archived_student_id, name, registered_date, registered_by = archive_row
        cursor.execute(
            """
            INSERT INTO students (student_id, name, registered_date, registered_by)
            VALUES (?, ?, ?, ?)
            """,
            (archived_student_id, name, registered_date, registered_by),
        )
        cursor.execute("DELETE FROM students_archive WHERE student_id = ?", (student_id,))
        connection.commit()
        return True


def mark_attendance(student_id: str, name: str) -> bool:
    init_db()
    today = _current_date()
    current_time = _current_time()

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT 1 FROM attendance WHERE student_id = ? AND date = ? LIMIT 1",
            (student_id, today),
        )
        if cursor.fetchone() is not None:
            return False

        cursor.execute(
            "INSERT INTO attendance (student_id, name, date, time) VALUES (?, ?, ?, ?)",
            (student_id, name, today, current_time),
        )
        connection.commit()
        return True


def get_attendance_by_date(date: str) -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, student_id, name, date, time FROM attendance WHERE date = ? ORDER BY time ASC, id ASC",
            (date,),
        )
        return cursor.fetchall()


def get_today_attendance() -> list[tuple[int, str, str, str, str]]:
    return get_attendance_by_date(_current_date())


def get_all_students() -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, student_id, name, registered_date, registered_by FROM students ORDER BY id ASC"
        )
        return cursor.fetchall()


def get_archive() -> list[tuple[int, str, str, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT id, student_id, name, registered_date, registered_by, deleted_by, deleted_date
            FROM students_archive
            ORDER BY deleted_date DESC, id DESC
            """
        )
        return cursor.fetchall()


def add_admin(username: str, password: str, created_by: str, role: str = "admin") -> None:
    init_db()
    username = username.strip()
    created_by = created_by.strip()
    role = role.strip().lower()
    if not username or not password or not created_by:
        raise ValueError("username, password, and created_by are required.")
    if role not in {"admin", "superadmin"}:
        raise ValueError("role must be 'admin' or 'superadmin'.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT 1 FROM admins WHERE username = ? LIMIT 1", (username,))
        if cursor.fetchone() is not None:
            raise ValueError(f"Admin username already exists: {username}")

        cursor.execute(
            """
            INSERT INTO admins (username, password_hash, role, created_by, created_date)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, _hash_password(password), role, created_by, _current_timestamp()),
        )
        connection.commit()


def get_all_admins() -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, username, role, created_by, created_date FROM admins ORDER BY created_date DESC, id DESC"
        )
        return cursor.fetchall()


def soft_delete_admin(username: str, deleted_by: str) -> bool:
    init_db()
    username = username.strip()
    deleted_by = deleted_by.strip()

    if not username or not deleted_by:
        raise ValueError("username and deleted_by are required.")
    if username == DEFAULT_SUPERADMIN_USERNAME:
        raise ValueError("The default superadmin account cannot be deleted.")

    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, username, password_hash, role, created_by, created_date FROM admins WHERE username = ? LIMIT 1",
            (username,),
        )
        admin_row = cursor.fetchone()
        if admin_row is None:
            return False

        admin_role = admin_row[3]
        if admin_role == "superadmin":
            cursor.execute("SELECT COUNT(*) FROM admins WHERE role = 'superadmin'")
            superadmin_count = cursor.fetchone()[0]
            if superadmin_count <= 1:
                raise ValueError("At least one superadmin account must remain active.")

        cursor.execute("DELETE FROM admins_archive WHERE username = ?", (username,))
        cursor.execute(
            """
            INSERT INTO admins_archive (
                id, username, password_hash, role, created_by, created_date, deleted_by, deleted_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*admin_row, deleted_by, _current_timestamp()),
        )
        cursor.execute("DELETE FROM admins WHERE username = ?", (username,))
        connection.commit()
        return True


def verify_admin(username: str, password: str) -> str | None:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT role, password_hash FROM admins WHERE username = ? LIMIT 1",
            (username.strip(),),
        )
        admin_row = cursor.fetchone()
        if admin_row is None:
            return None

        role, password_hash = admin_row
        if password_hash == _hash_password(password):
            return role
        return None


def log_action(admin_username: str, action: str, details: str) -> None:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO audit_log (admin_username, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (admin_username, action, details, _current_timestamp()),
        )
        connection.commit()


def log_export(admin_username: str, export_type: str, filename: str) -> None:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO exports_log (admin_username, export_type, filename, timestamp) VALUES (?, ?, ?, ?)",
            (admin_username, export_type, filename, _current_timestamp()),
        )
        connection.commit()


def get_audit_log() -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, admin_username, action, details, timestamp FROM audit_log ORDER BY timestamp DESC, id DESC"
        )
        return cursor.fetchall()


def get_exports_log() -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, admin_username, export_type, filename, timestamp FROM exports_log ORDER BY timestamp DESC, id DESC"
        )
        return cursor.fetchall()


def get_all_attendance() -> list[tuple[int, str, str, str, str]]:
    init_db()
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, student_id, name, date, time FROM attendance ORDER BY date ASC, time ASC, id ASC"
        )
        return cursor.fetchall()


if __name__ == "__main__":
    init_db()