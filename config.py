"""
config.py - Handles loading and saving bot configuration from config.json
"""

import json
import os

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "bot_token": "",
    "admin_id": 0,
    "log_channel_id": None,
    "force_channel": None,
    "force_group": None,
    "autodelete_mode": "off",       # "off", "30s", "10m", "1h", or seconds as int
    "autodelete_seconds": 0,
    "autodelete_type": "full",      # "full", "hide", "admin_only"
    "per_user_autodelete": {},       # { "user_id": seconds }
    "blocked_users": []
}


def load_config() -> dict:
    """Load config from file, create if missing."""
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Merge missing keys from defaults
    for key, val in DEFAULT_CONFIG.items():
        if key not in data:
            data[key] = val
    return data


def save_config(config: dict):
    """Save config dict to file."""
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def parse_time_string(time_str: str) -> int:
    """
    Parse time strings like '30s', '10m', '1h', '2d' into seconds.
    Returns 0 if invalid or 'off'.
    """
    time_str = time_str.strip().lower()
    if time_str == "off":
        return -1  # special marker for "off"
    try:
        if time_str.endswith("s"):
            return int(time_str[:-1])
        elif time_str.endswith("m"):
            return int(time_str[:-1]) * 60
        elif time_str.endswith("h"):
            return int(time_str[:-1]) * 3600
        elif time_str.endswith("d"):
            return int(time_str[:-1]) * 86400
        else:
            return int(time_str)  # raw seconds
    except ValueError:
        return 0
