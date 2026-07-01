import functools
import hashlib
from datetime import date, datetime

import mysql.connector
from mysql.connector import pooling

from core.config import get_db_config
from core.logger import get_logger
from core.errors import (
    DatabaseUnavailableError,
    DatabaseOperationError,
    DB_UNAVAILABLE,
    DB_INIT_FAILED,
    DB_WRITE_FAILED,
)

_log = get_logger(__name__)

_pool: pooling.MySQLConnectionPool | None = None


# ---------------------------------------------------------------------------
# Internal decorator helpers
# ---------------------------------------------------------------------------

def _safe_read(default):
    """Catch any DB error in a read function, log it, and return *default*."""
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (DatabaseUnavailableError, DatabaseOperationError):
                raise
            except Exception:
                _log.exception("DB read error in %s", fn.__name__)
                return default() if callable(default) else default
        return wrapper
    return decorator


def _safe_write(fn):
    """Catch any DB error in a write function, log it, and raise DatabaseOperationError."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (DatabaseUnavailableError, DatabaseOperationError):
            raise
        except Exception:
            _log.exception("DB write error in %s", fn.__name__)
            raise DatabaseOperationError(DB_WRITE_FAILED) from None
    return wrapper


def _safe_soft(fn):
    """Like _safe_write but swallows the error (for non-critical audit/log writes)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception:
            _log.exception("Non-critical DB write failed in %s", fn.__name__)
            return None
    return wrapper


# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        try:
            cfg = get_db_config()
            bare = mysql.connector.connect(
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
            )
            cur = bare.cursor()
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{cfg['database']}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cur.close()
            bare.close()

            _pool = pooling.MySQLConnectionPool(
                pool_name="attendance_pool",
                pool_size=5,
                host=cfg["host"],
                port=cfg["port"],
                user=cfg["user"],
                password=cfg["password"],
                database=cfg["database"],
                charset="utf8mb4",
                collation="utf8mb4_unicode_ci",
            )
            _log.info("Database connection pool created (%s:%s/%s)", cfg["host"], cfg["port"], cfg["database"])
        except Exception as exc:
            _log.exception("Failed to create database connection pool")
            raise DatabaseUnavailableError(DB_UNAVAILABLE, cause=exc) from exc
    return _pool


def get_connection() -> mysql.connector.MySQLConnection:
    return _get_pool().get_connection()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------

def init_db() -> None:
    conn = None
    cur = None
    try:
        conn = get_connection()
        cur = conn.cursor()

        table_statements = [
            (
                "system_config",
                """
                CREATE TABLE IF NOT EXISTS system_config (
                    `key`   VARCHAR(100) PRIMARY KEY,
                    `value` VARCHAR(255) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "admins",
                """
                CREATE TABLE IF NOT EXISTS admins (
                    id            INT AUTO_INCREMENT PRIMARY KEY,
                    username      VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role          ENUM('superadmin','admin') NOT NULL,
                    created_by    VARCHAR(100),
                    created_date  DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "classes",
                """
                CREATE TABLE IF NOT EXISTS classes (
                    id           INT AUTO_INCREMENT PRIMARY KEY,
                    name         VARCHAR(100) NOT NULL,
                    section      VARCHAR(50)  NOT NULL,
                    max_students INT DEFAULT 30,
                    late_cutoff  TIME DEFAULT '06:30:00',
                    absent_cutoff TIME DEFAULT '07:00:00',
                    class_start_time TIME DEFAULT '06:00:00',
                    class_end_time TIME DEFAULT '10:00:00',
                    created_by   VARCHAR(100),
                    created_date DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "attendance_finalization",
                """
                CREATE TABLE IF NOT EXISTS attendance_finalization (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    class_id INT NOT NULL,
                    date DATE NOT NULL,
                    finalized_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY uq_class_date (class_id, date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "students",
                """
                CREATE TABLE IF NOT EXISTS students (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    student_id      VARCHAR(50) UNIQUE NOT NULL,
                        name            VARCHAR(300) NOT NULL,
                        first_name      VARCHAR(100) NOT NULL,
                        middle_name     VARCHAR(100),
                        last_name       VARCHAR(100) NOT NULL,
                        profile_photo   LONGBLOB,
                    class_id        INT,
                    registered_by   VARCHAR(100),
                    registered_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE SET NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "students_archive",
                """
                CREATE TABLE IF NOT EXISTS students_archive (
                    id              INT AUTO_INCREMENT PRIMARY KEY,
                    student_id      VARCHAR(50) NOT NULL,
                        name            VARCHAR(300) NOT NULL,
                        first_name      VARCHAR(100) NOT NULL,
                        middle_name     VARCHAR(100),
                        last_name       VARCHAR(100) NOT NULL,
                        profile_photo   LONGBLOB,
                    class_id        INT,
                    registered_by   VARCHAR(100),
                    registered_date DATETIME,
                    deleted_by      VARCHAR(100),
                    deleted_date    DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "attendance",
                """
                CREATE TABLE IF NOT EXISTS attendance (
                    id         INT AUTO_INCREMENT PRIMARY KEY,
                    student_id VARCHAR(50)  NOT NULL,
                    name       VARCHAR(100) NOT NULL,
                    class_id   INT,
                    date       DATE         NOT NULL,
                    time       TIME         NOT NULL,
                    status     ENUM('present','late','absent') DEFAULT 'present'
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "audit_log",
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id             INT AUTO_INCREMENT PRIMARY KEY,
                    admin_username VARCHAR(100),
                    action         VARCHAR(255),
                    details        TEXT,
                    timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
            (
                "exports_log",
                """
                CREATE TABLE IF NOT EXISTS exports_log (
                    id             INT AUTO_INCREMENT PRIMARY KEY,
                    admin_username VARCHAR(100),
                    export_type    VARCHAR(50),
                    filename       VARCHAR(255),
                    timestamp      DATETIME DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """,
            ),
        ]

        for table_name, statement in table_statements:
            cur.execute(statement)
            conn.commit()
            _log.info("Ensured table: %s", table_name)

        conn.commit()

        _migrations = [
            "ALTER TABLE students ADD COLUMN date_of_birth DATE NULL",
            "ALTER TABLE students ADD COLUMN address TEXT NULL",
            "ALTER TABLE students_archive ADD COLUMN date_of_birth DATE NULL",
            "ALTER TABLE students_archive ADD COLUMN address TEXT NULL",
        ]
        for _msql in _migrations:
            try:
                cur.execute(_msql)
                conn.commit()
            except Exception:
                pass  # column already exists — skip

        cur.execute("SELECT id FROM admins WHERE role = 'superadmin' LIMIT 1")
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO admins (username, password_hash, role, created_by) VALUES (%s, %s, %s, %s)",
                ("superadmin", _hash("super123"), "superadmin", "system"),
            )

        defaults = [
            ("max_classes", "20"),
            ("late_cutoff", "06:30"),
            ("absent_cutoff", "07:00"),
        ]
        for key, value in defaults:
            cur.execute(
                "INSERT IGNORE INTO system_config (`key`, `value`) VALUES (%s, %s)",
                (key, value),
            )

        conn.commit()
        _log.info("Database initialization complete")

    except DatabaseUnavailableError:
        raise
    except Exception as exc:
        _log.exception("Database initialization failed")
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        raise DatabaseUnavailableError(DB_INIT_FAILED, cause=exc) from exc
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
        if conn is not None:
            try:
                if conn.is_connected():
                    conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

@_safe_write
def add_class(
    name: str,
    section: str,
    created_by: str,
    max_students: int = 30,
    late_cutoff: str | None = None,
    absent_cutoff: str | None = None,
    class_start_time: str | None = None,
    class_end_time: str | None = None,
) -> int:
    """Add a class with optional time cutoffs (HH:MM or HH:MM:SS)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO classes (name, section, max_students, late_cutoff, absent_cutoff, class_start_time, class_end_time, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (name, section, max_students, late_cutoff, absent_cutoff, class_start_time, class_end_time, created_by),
        )
        conn.commit()
        new_id = cur.lastrowid
        cur.close()
        return new_id
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_all_classes() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM classes ORDER BY name, section")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_all_classes_with_times() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, name, section, max_students, late_cutoff, absent_cutoff, class_start_time, class_end_time, "
            "COALESCE(class_end_time, (SELECT `value` FROM system_config WHERE `key` = 'absent_cutoff' LIMIT 1)) AS effective_end_time, "
            "created_by, created_date FROM classes ORDER BY name, section"
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def update_all_class_times(late_cutoff: str | None, absent_cutoff: str | None) -> int:
    """Update late_cutoff and absent_cutoff on all classes. Returns number of rows updated."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE classes SET late_cutoff = %s, absent_cutoff = %s",
            (late_cutoff, absent_cutoff),
        )
        conn.commit()
        return cur.rowcount if cur.rowcount is not None else 0
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read((None, None))
def get_class_cutoffs(class_id: int) -> tuple[str | None, str | None]:
    """Return (late_cutoff, absent_cutoff) as strings 'HH:MM[:SS]' or (None, None)."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT late_cutoff, absent_cutoff FROM classes WHERE id = %s LIMIT 1", (class_id,))
        row = cur.fetchone()
        cur.close()
        if not row:
            return (None, None)
        late, absent = row[0], row[1]
        try:
            if hasattr(late, "strftime"):
                late = late.strftime("%H:%M")
        except Exception:
            pass
        try:
            if hasattr(absent, "strftime"):
                absent = absent.strftime("%H:%M")
        except Exception:
            pass
        return (late, absent)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def delete_class(class_id: int, deleted_by: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM classes WHERE id = %s", (class_id,))
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    log_action(deleted_by, "DELETE_CLASS", f"class_id={class_id}")


@_safe_read(0)
def get_class_count() -> int:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM classes")
        count = cur.fetchone()[0]
        cur.close()
        return count
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_max_classes() -> int:
    value = get_system_config("max_classes")
    return int(value) if value is not None else 20


def update_max_classes(new_limit: int) -> None:
    update_system_config("max_classes", str(new_limit))


# ---------------------------------------------------------------------------
# Students
# ---------------------------------------------------------------------------

@_safe_write
def add_student(
    student_id: str,
    first_name: str,
    middle_name: str | None,
    last_name: str,
    class_id: int,
    registered_by: str,
    profile_photo: bytes | None = None,
    date_of_birth: str | None = None,
    address: str | None = None,
) -> None:
    if middle_name and str(middle_name).strip():
        name = f"{first_name.strip()} {str(middle_name).strip()} {last_name.strip()}"
    else:
        name = f"{first_name.strip()} {last_name.strip()}"

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO students (student_id, name, first_name, middle_name, last_name, "
            "class_id, registered_by, profile_photo, date_of_birth, address) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (student_id, name, first_name, middle_name, last_name,
             class_id, registered_by, profile_photo, date_of_birth, address),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read(None)
def get_student_profile(student_id: str) -> dict | None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, student_id, name, first_name, middle_name, last_name, class_id, "
            "registered_by, registered_date, profile_photo, date_of_birth, address "
            "FROM students WHERE student_id = %s LIMIT 1",
            (student_id,),
        )
        row = cur.fetchone()
        cur.close()
        return row
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def update_student(
    student_id: str,
    first_name: str,
    middle_name: str | None,
    last_name: str,
    date_of_birth: str | None = None,
    address: str | None = None,
) -> None:
    """Update editable fields on a student record."""
    mn = str(middle_name).strip() if middle_name and str(middle_name).strip() else None
    if mn:
        name = f"{first_name.strip()} {mn} {last_name.strip()}"
    else:
        name = f"{first_name.strip()} {last_name.strip()}"

    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE students SET name=%s, first_name=%s, middle_name=%s, last_name=%s, "
            "date_of_birth=%s, address=%s WHERE student_id=%s",
            (name, first_name.strip(), mn, last_name.strip(),
             date_of_birth or None, address or None, student_id),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def update_student_photo(student_id: str, photo_bytes: bytes | None) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "UPDATE students SET profile_photo = %s WHERE student_id = %s",
            (photo_bytes, student_id),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_students_by_class(class_id: int) -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, student_id, name, first_name, middle_name, last_name, class_id, registered_by, registered_date FROM students WHERE class_id = %s ORDER BY name",
            (class_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_all_students() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT id, student_id, name, first_name, middle_name, last_name, class_id, registered_by, registered_date FROM students ORDER BY name",
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def soft_delete_student(student_id: str, deleted_by: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
        student = cur.fetchone()
        if student:
            cur.execute(
                """INSERT INTO students_archive
                   (student_id, name, first_name, middle_name, last_name, profile_photo,
                    class_id, registered_by, registered_date, deleted_by, date_of_birth, address)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    student["student_id"],
                    student.get("name"),
                    student.get("first_name"),
                    student.get("middle_name"),
                    student.get("last_name"),
                    student.get("profile_photo"),
                    student.get("class_id"),
                    student.get("registered_by"),
                    student.get("registered_date"),
                    deleted_by,
                    student.get("date_of_birth"),
                    student.get("address"),
                ),
            )
            cur.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
            conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def restore_student(student_id: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
        existing = cur.fetchone()
        if existing:
            raise RuntimeError("Cannot restore — a student with this ID is already active.")

        cur.execute(
            "SELECT * FROM students_archive WHERE student_id = %s ORDER BY deleted_date DESC LIMIT 1",
            (student_id,),
        )
        record = cur.fetchone()
        if record:
            cur.execute(
                """INSERT INTO students
                   (student_id, name, first_name, middle_name, last_name, profile_photo,
                    class_id, registered_by, registered_date, date_of_birth, address)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    record["student_id"],
                    record.get("name"),
                    record.get("first_name"),
                    record.get("middle_name"),
                    record.get("last_name"),
                    record.get("profile_photo"),
                    record.get("class_id"),
                    record.get("registered_by"),
                    record.get("registered_date"),
                    record.get("date_of_birth"),
                    record.get("address"),
                ),
            )
            cur.execute("DELETE FROM students_archive WHERE student_id = %s", (student_id,))
            conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_todays_birthdays() -> list[dict]:
    """Return active students whose birth month+day matches today."""
    from datetime import date as _date
    today = _date.today()
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT student_id, name, first_name, middle_name, last_name, date_of_birth, class_id "
            "FROM students "
            "WHERE date_of_birth IS NOT NULL "
            "  AND MONTH(date_of_birth) = %s AND DAY(date_of_birth) = %s "
            "ORDER BY name",
            (today.month, today.day),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def hard_delete_student(student_id: str) -> int:
    """Permanently delete a student and their attendance records.

    Executes deletions in a single transaction. If any delete fails,
    the transaction is rolled back. Returns the number of attendance
    records deleted.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM attendance WHERE student_id = %s", (student_id,))
        attendance_deleted = cur.rowcount if cur.rowcount is not None else 0
        cur.execute("DELETE FROM students_archive WHERE student_id = %s", (student_id,))
        cur.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        conn.commit()
        cur.close()
        return int(attendance_deleted)
    except Exception:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        _log.exception("hard_delete_student failed for student_id=%s", student_id)
        raise DatabaseOperationError(DB_WRITE_FAILED) from None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_archive() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM students_archive ORDER BY deleted_date DESC")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------

@_safe_write
def mark_attendance(student_id: str, name: str, class_id: int, status: str = "present") -> bool:
    """Mark attendance for a student once per day.

    Returns True if a new attendance record was inserted, False if a record
    for this student already exists for today (no-op).
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, status FROM attendance WHERE student_id = %s AND date = CURDATE() LIMIT 1", (student_id,))
        row = cur.fetchone()

        now = datetime.now()
        if row is None:
            cur.execute(
                "INSERT INTO attendance (student_id, name, class_id, date, time, status) VALUES (%s, %s, %s, %s, %s, %s)",
                (student_id, name, class_id, now.date(), now.time(), status),
            )
            conn.commit()
            cur.close()
            return True

        existing_id, existing_status = row[0], row[1]
        if (existing_status == "absent") and (status in ("present", "late")):
            cur.execute(
                "UPDATE attendance SET status = %s, time = %s, name = %s, class_id = %s WHERE id = %s",
                (status, now.time(), name, class_id, existing_id),
            )
            conn.commit()
            cur.close()
            return True

        cur.close()
        return False
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_attendance_by_date(attendance_date: date, class_id: int | None = None) -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        if class_id is not None:
            cur.execute(
                "SELECT * FROM attendance WHERE date = %s AND class_id = %s ORDER BY time",
                (attendance_date, class_id),
            )
        else:
            cur.execute(
                "SELECT * FROM attendance WHERE date = %s ORDER BY time",
                (attendance_date,),
            )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_attendance_by_student(student_id: str) -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT * FROM attendance WHERE student_id = %s ORDER BY date DESC, time DESC",
            (student_id,),
        )
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_today_attendance(class_id: int | None = None) -> list[dict]:
    return get_attendance_by_date(date.today(), class_id)


def finalize_attendance(class_id: int, attendance_date: date) -> int:
    """Ensure every student in `class_id` has an attendance record for `attendance_date`.

    Inserts missing records with status 'absent' and current time. Returns number inserted.
    """
    inserted = 0
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        students = get_students_by_class(class_id) or []
        existing = get_attendance_by_date(attendance_date, class_id) or []
        present_ids = {str(r.get("student_id")) for r in existing}
        cur.execute("SELECT class_end_time FROM classes WHERE id = %s LIMIT 1", (class_id,))
        row = cur.fetchone()
        class_end = row[0] if row else None
        try:
            if hasattr(class_end, "strftime"):
                class_end_time = class_end
            else:
                class_end_time = None
        except Exception:
            class_end_time = None

        use_time = class_end_time if class_end_time is not None else datetime.now().time()

        for s in students:
            sid = str(s.get("student_id"))
            name = s.get("name") or f"{s.get('first_name','')} {s.get('last_name','')}"
            if sid in present_ids:
                continue
            cur.execute(
                "INSERT INTO attendance (student_id, name, class_id, date, time, status) VALUES (%s, %s, %s, %s, %s, %s)",
                (sid, name, class_id, attendance_date, use_time, "absent"),
            )
            inserted += 1
        if inserted:
            conn.commit()
            try:
                mark_attendance_finalized(class_id, attendance_date)
            except Exception:
                _log.warning("finalize_attendance: could not mark finalization for class_id=%s date=%s", class_id, attendance_date)
        cur.close()
    except (DatabaseUnavailableError, DatabaseOperationError):
        raise
    except Exception:
        _log.exception("finalize_attendance failed for class_id=%s date=%s", class_id, attendance_date)
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise DatabaseOperationError(DB_WRITE_FAILED) from None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
    return inserted


# ---------------------------------------------------------------------------
# Admins
# ---------------------------------------------------------------------------

@_safe_write
def add_admin(username: str, password: str, role: str, created_by: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO admins (username, password_hash, role, created_by) VALUES (%s, %s, %s, %s)",
            (username, _hash(password), role, created_by),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_all_admins() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, username, role, created_by, created_date FROM admins ORDER BY username")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def delete_admin(username: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM admins WHERE username = %s", (username,))
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def verify_admin(username: str, password: str) -> str | None:
    """Return the admin's role string, or None for wrong credentials.

    Raises DatabaseUnavailableError if the database cannot be reached.
    """
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT role FROM admins WHERE username = %s AND password_hash = %s",
            (username, _hash(password)),
        )
        row = cur.fetchone()
        cur.close()
        return row["role"] if row else None
    except DatabaseUnavailableError:
        raise
    except Exception:
        _log.exception("verify_admin failed for username=%s", username)
        raise DatabaseUnavailableError(
            "Unable to verify credentials. Please check the database connection and try again."
        ) from None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Audit / Export logs
# ---------------------------------------------------------------------------

@_safe_soft
def log_action(admin_username: str, action: str, details: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO audit_log (admin_username, action, details) VALUES (%s, %s, %s)",
            (admin_username, action, details),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_soft
def log_export(admin_username: str, export_type: str, filename: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO exports_log (admin_username, export_type, filename) VALUES (%s, %s, %s)",
            (admin_username, export_type, filename),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_audit_log() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM audit_log ORDER BY timestamp DESC")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read([])
def get_exports_log() -> list[dict]:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM exports_log ORDER BY timestamp DESC")
        rows = cur.fetchall()
        cur.close()
        return rows
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


# ---------------------------------------------------------------------------
# System config
# ---------------------------------------------------------------------------

@_safe_read(None)
def get_system_config(key: str) -> str | None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT `value` FROM system_config WHERE `key` = %s", (key,))
        row = cur.fetchone()
        cur.close()
        return row[0] if row else None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_read(False)
def is_attendance_finalized(class_id: int, attendance_date: date) -> bool:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM attendance_finalization WHERE class_id = %s AND date = %s LIMIT 1", (class_id, attendance_date))
        row = cur.fetchone()
        cur.close()
        return row is not None
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_soft
def mark_attendance_finalized(class_id: int, attendance_date: date) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT IGNORE INTO attendance_finalization (class_id, date) VALUES (%s, %s)",
            (class_id, attendance_date),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def reset_todays_attendance(class_id: int, attendance_date: date) -> int:
    """Delete attendance records for the given class and date. Returns rows deleted."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM attendance WHERE class_id = %s AND date = %s", (class_id, attendance_date))
        deleted = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        cur.close()
        return int(deleted)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def reset_finalization(class_id: int, attendance_date: date) -> int:
    """Delete finalization record for the given class and date. Returns rows deleted."""
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM attendance_finalization WHERE class_id = %s AND date = %s", (class_id, attendance_date))
        deleted = cur.rowcount if cur.rowcount is not None else 0
        conn.commit()
        cur.close()
        return int(deleted)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


@_safe_write
def update_system_config(key: str, value: str) -> None:
    conn = None
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO system_config (`key`, `value`) VALUES (%s, %s) "
            "ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)",
            (key, value),
        )
        conn.commit()
        cur.close()
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
