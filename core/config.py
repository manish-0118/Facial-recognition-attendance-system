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


