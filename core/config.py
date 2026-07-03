import configparser
import os
from core.paths import data_dir

CONFIG_PATH = os.path.join(data_dir(), "config.ini")

DEFAULTS = {
    "database": {
        "host": "localhost",
        "port": "3306",
        "user": "root",
        "password": "Nihareeka@123",
        "database": "attendance_system_db",
    },
    "app": {
        "late_cutoff_time": "06:30",
        "absent_cutoff_time": "07:00",
        "max_classes": "20",
        "backup_frequency": "daily",
    },
}


_config_cache: configparser.ConfigParser | None = None


def _load_config() -> configparser.ConfigParser:
    global _config_cache
    if _config_cache is not None:
        return _config_cache
    config = configparser.ConfigParser(interpolation=None)
    if not os.path.exists(CONFIG_PATH):
        for section, values in DEFAULTS.items():
            config[section] = values
        with open(CONFIG_PATH, "w") as f:
            config.write(f)
    else:
        config.read(CONFIG_PATH)
    _config_cache = config
    return config


def get_db_config() -> dict:
    config = _load_config()
    db = config["database"]
    return {
        "host": db.get("host", DEFAULTS["database"]["host"]),
        "port": int(db.get("port", DEFAULTS["database"]["port"])),
        "user": db.get("user", DEFAULTS["database"]["user"]),
        "password": db.get("password", DEFAULTS["database"]["password"]),
        "database": db.get("database", DEFAULTS["database"]["database"]),
    }


def get_app_config() -> dict:
    config = _load_config()
    app = config["app"]
    return {
        "late_cutoff_time": app.get("late_cutoff_time", DEFAULTS["app"]["late_cutoff_time"]),
        "absent_cutoff_time": app.get("absent_cutoff_time", DEFAULTS["app"]["absent_cutoff_time"]),
        "max_classes": int(app.get("max_classes", DEFAULTS["app"]["max_classes"])),
        "backup_frequency": app.get("backup_frequency", DEFAULTS["app"]["backup_frequency"]),
    }


def update_config(section: str, key: str, value: str) -> None:
    config = _load_config()
    if section not in config:
        config[section] = {}
    config[section][key] = str(value)
    with open(CONFIG_PATH, "w") as f:
        config.write(f)
