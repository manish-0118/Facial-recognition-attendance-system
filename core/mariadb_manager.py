import os
import sys
import time
import socket
import subprocess

_server_proc = None
_CREATE_NO_WINDOW = 0x08000000


def _write_my_ini(path, data_dir, plugin_dir, port):
    # Forward slashes — backslashes in MariaDB ini paths cause errors
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


def is_bundled() -> bool:
    return getattr(sys, 'frozen', False)


def _read_mariadb_config() -> dict:
    import configparser
    from core.paths import data_dir
    config_ini = os.path.join(data_dir(), "config.ini")
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(config_ini)
    return {
        "port":     cfg.get("mariadb_internal", "port",          fallback="3307"),
        "data_dir": cfg.get("mariadb_internal", "data_dir",      fallback=""),
        "root_pw":  cfg.get("mariadb_internal", "root_password", fallback=""),
    }


def _wait_for_port(port: int, timeout: int = 45) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def start_server() -> bool:
    """Start the bundled MariaDB server. Returns True on success."""
    global _server_proc
    if not is_bundled():
        return True  # dev mode — use system MySQL

    # Binaries live in Program Files (read-only, that's fine)
    install_dir = os.path.dirname(sys.executable)
    mariadb_dir = os.path.join(install_dir, "mariadb")
    mysqld      = os.path.join(mariadb_dir, "bin", "mysqld.exe")
    plugin_dir  = os.path.join(mariadb_dir, "lib", "plugin")

    if not os.path.exists(mysqld):
        return False

    # All writable files are in AppData\Roaming (always user-writable)
    from core.paths import data_dir as _data_dir
    writable_dir = _data_dir()
    my_ini       = os.path.join(writable_dir, "my.ini")

    info     = _read_mariadb_config()
    port     = int(info["port"])
    db_data  = info["data_dir"] or os.path.join(writable_dir, "data")

    # Data directory must exist — if not, setup_db didn't complete
    if not os.path.isdir(db_data):
        return False

    # Already running?
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        pass

    # Write my.ini to the writable directory (never touch Program Files)
    _write_my_ini(my_ini, db_data, plugin_dir, port)

    _server_proc = subprocess.Popen(
        [mysqld, f"--defaults-file={my_ini}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_CREATE_NO_WINDOW,
    )
    return _wait_for_port(port, timeout=45)


def stop_server() -> None:
    global _server_proc
    if _server_proc and _server_proc.poll() is None:
        try:
            _server_proc.terminate()
            _server_proc.wait(timeout=10)
        except Exception:
            try:
                _server_proc.kill()
            except Exception:
                pass
        _server_proc = None
        return

    # Called from a fresh process (e.g. --stop-db during uninstall).
    # _server_proc is None here, so use mysqladmin to shut down gracefully.
    if not is_bundled():
        return
    install_dir = os.path.dirname(sys.executable)
    mysqladmin  = os.path.join(install_dir, "mariadb", "bin", "mysqladmin.exe")
    if not os.path.exists(mysqladmin):
        return
    info    = _read_mariadb_config()
    port    = info["port"]
    root_pw = info["root_pw"]
    pw_arg  = f"--password={root_pw}" if root_pw else "--password="
    subprocess.run(
        [mysqladmin, "-h", "127.0.0.1", "-P", str(port),
         "-u", "root", pw_arg, "--connect-timeout=5", "shutdown"],
        capture_output=True,
        creationflags=_CREATE_NO_WINDOW,
    )
    _server_proc = None
