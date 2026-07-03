"""
Post-install database initialiser — called by Inno Setup after files are copied.
Usage (invoked via NihareekaAttendance.exe --setup-db <install_dir>):
    setup_db.main()  with sys.argv[1] = install_dir
"""
import os
import sys
import time
import string
import random
import socket
import subprocess
import configparser

CHARSET          = string.ascii_letters + string.digits + "!@#$%^&*"
DB_NAME          = "attendance_system_db"
DB_USER          = "attendance_app"
PORT             = 3307
CREATE_NO_WINDOW = 0x08000000


def _rnd_pw(length=20):
    return "".join(random.SystemRandom().choice(CHARSET) for _ in range(length))


def _wait_port(port, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2):
                return True
        except OSError:
            time.sleep(1)
    return False


def _write_my_ini(path, data_dir, plugin_dir, port):
    # Forward slashes — backslashes in MariaDB ini paths cause failures
    data_dir   = data_dir.replace("\\", "/")
    plugin_dir = plugin_dir.replace("\\", "/")
    content = (
        "[mysqld]\n"
        f"datadir={data_dir}\n"
        f"port={port}\n"
        f"plugin_dir={plugin_dir}\n"
        "bind-address=127.0.0.1\n"
        "character-set-server=utf8mb4\n"
        "collation-server=utf8mb4_unicode_ci\n"
        "default-authentication-plugin=mysql_native_password\n"
        "\n"
        "[client]\n"
        f"port={port}\n"
    )
    with open(path, "w") as f:
        f.write(content)


def _run_sql(mysql_cli, port, user, password, sql):
    pw_arg = f"--password={password}" if password else "--password="
    cmd = [
        mysql_cli, "-h", "127.0.0.1", "-P", str(port),
        "-u", user, pw_arg, "--connect-timeout=10", "-e", sql,
    ]
    return subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=CREATE_NO_WINDOW)


def main():
    install_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(sys.executable)

    # ── Binary paths (inside Program Files — read-only is fine) ──────────────
    mariadb_dir  = os.path.join(install_dir, "mariadb")
    mysqld       = os.path.join(mariadb_dir, "bin", "mysqld.exe")
    mysql_cli    = os.path.join(mariadb_dir, "bin", "mysql.exe")
    install_db   = os.path.join(mariadb_dir, "bin", "mariadb-install-db.exe")
    plugin_dir   = os.path.join(mariadb_dir, "lib", "plugin")

    # ── Writable paths (AppData\Roaming — always writable by current user) ────
    appdata  = os.environ.get("APPDATA", os.path.join(os.path.expanduser("~"), "AppData", "Roaming"))
    app_data = os.path.join(appdata, "NihareekaAttendance")
    os.makedirs(app_data, exist_ok=True)
    data_dir    = os.path.join(app_data, "data")
    my_ini      = os.path.join(app_data, "my.ini")
    config_ini  = os.path.join(app_data, "config.ini")

    fresh_install = not os.path.isdir(data_dir)
    root_pw = ""
    app_pw  = _rnd_pw(20)

    # ── Re-install: read existing credentials ────────────────────────────────
    if not fresh_install and os.path.exists(config_ini):
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(config_ini)
        root_pw = cfg.get("mariadb_internal", "root_password", fallback="")
        app_pw  = cfg.get("database",         "password",      fallback=app_pw)

    # ── 1. Initialise data directory (first install only) ────────────────────
    os.makedirs(data_dir, exist_ok=True)
    _write_my_ini(my_ini, data_dir, plugin_dir, PORT)

    if fresh_install:
        print("Initialising MariaDB data directory...")
        result = subprocess.run(
            [install_db, f"--datadir={data_dir}"],
            capture_output=True, text=True,
            creationflags=CREATE_NO_WINDOW,
        )
        if result.returncode != 0:
            print("ERROR: MariaDB initialisation failed:\n", result.stdout, result.stderr)
            sys.exit(1)
        print("Data directory initialised.")

    # ── 2. Start MariaDB server ───────────────────────────────────────────────
    print("Starting MariaDB server...")
    srv = subprocess.Popen(
        [mysqld, f"--defaults-file={my_ini}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=CREATE_NO_WINDOW,
    )

    if not _wait_port(PORT, timeout=90):
        print("ERROR: MariaDB did not start within 90 seconds.")
        srv.terminate()
        sys.exit(1)
    print("MariaDB server ready.")

    # ── 3. Set root password (first install — root has no password yet) ───────
    if fresh_install:
        new_root_pw = _rnd_pw(24)
        r = _run_sql(mysql_cli, PORT, "root", "",
                     f"ALTER USER 'root'@'localhost' IDENTIFIED BY '{new_root_pw}'; "
                     f"FLUSH PRIVILEGES;")
        if r.returncode != 0:
            r = _run_sql(mysql_cli, PORT, "root", "",
                         f"SET PASSWORD = PASSWORD('{new_root_pw}'); "
                         f"FLUSH PRIVILEGES;")
        root_pw = new_root_pw if r.returncode == 0 else ""

    # ── 4. Create database + app user ─────────────────────────────────────────
    sql = (
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; "
        f"CREATE USER IF NOT EXISTS '{DB_USER}'@'127.0.0.1' "
        f"IDENTIFIED BY '{app_pw}'; "
        f"GRANT ALL PRIVILEGES ON `{DB_NAME}`.* TO '{DB_USER}'@'127.0.0.1'; "
        f"FLUSH PRIVILEGES;"
    )
    r = _run_sql(mysql_cli, PORT, "root", root_pw, sql)
    if r.returncode != 0:
        print("ERROR: Could not create database/user:\n", r.stderr)
        srv.terminate()
        sys.exit(1)
    print(f"Database '{DB_NAME}' and user '{DB_USER}' ready.")

    # ── 5. Write config.ini to AppData ───────────────────────────────────────
    cfg = configparser.ConfigParser(interpolation=None)
    cfg["database"] = {
        "host": "127.0.0.1", "port": str(PORT),
        "user": DB_USER, "password": app_pw, "database": DB_NAME,
    }
    cfg["app"] = {
        "late_cutoff_time": "06:30", "absent_cutoff_time": "07:00",
        "max_classes": "20", "backup_frequency": "daily",
    }
    cfg["mariadb_internal"] = {
        "root_password": root_pw, "port": str(PORT), "data_dir": data_dir,
    }
    with open(config_ini, "w") as f:
        cfg.write(f)
    print("config.ini written.")

    # ── 6. Create app tables ──────────────────────────────────────────────────
    try:
        from core.database import init_db
        init_db()
        print("Application tables created.")
    except Exception as exc:
        print(f"WARNING: init_db: {exc}")

    srv.terminate()
    print("Setup complete.")


if __name__ == "__main__":
    main()
