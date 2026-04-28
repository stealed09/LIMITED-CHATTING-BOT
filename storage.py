"""
storage.py - JSON-based storage for users, message tracking, and log mapping.
All data persists in users.json. Message tracking is in-memory (cleared on restart).
"""

import json
import os
import time
from threading import Lock

USERS_FILE = "users.json"
_lock = Lock()

# In-memory message tracking for auto-delete: { msg_key: {"chat_id": x, "msg_id": x, "ts": x} }
_pending_deletes: dict = {}

# In-memory: maps user_id -> admin_message_id (the forwarded msg in admin chat)
# so admin can reply to correct user
_admin_msg_to_user: dict = {}   # admin_msg_id -> user_id
_user_to_admin_msg: dict = {}   # user_id -> latest admin_msg_id


def load_users() -> dict:
    """Load all users from users.json."""
    if not os.path.exists(USERS_FILE):
        return {}
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_users(users: dict):
    """Save users dict to users.json."""
    with _lock:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2, ensure_ascii=False)


def get_user(user_id: int) -> dict | None:
    """Get a single user by ID."""
    users = load_users()
    return users.get(str(user_id))


def upsert_user(user_id: int, name: str, username: str | None):
    """
    Insert or update user record.
    Also initializes log_msg_id and message history if missing.
    """
    users = load_users()
    uid = str(user_id)
    if uid not in users:
        users[uid] = {
            "user_id": user_id,
            "name": name,
            "username": username or "",
            "log_msg_id": None,        # message ID in log channel
            "history": [],             # list of {"role": "user"/"admin", "text": "...", "ts": 0}
            "msg_ids": [],             # list of {"chat_id": x, "msg_id": x} for delete chat
            "joined_at": int(time.time())
        }
    else:
        # Update name/username in case they changed
        users[uid]["name"] = name
        users[uid]["username"] = username or ""
        # Ensure new fields exist for old records
        if "log_msg_id" not in users[uid]:
            users[uid]["log_msg_id"] = None
        if "history" not in users[uid]:
            users[uid]["history"] = []
        if "msg_ids" not in users[uid]:
            users[uid]["msg_ids"] = []
    save_users(users)
    return users[uid]


def set_log_msg_id(user_id: int, msg_id: int):
    """Store the log channel message ID for a user."""
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["log_msg_id"] = msg_id
        save_users(users)


def append_history(user_id: int, role: str, text: str):
    """Append a message to the user's chat history."""
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["history"].append({
            "role": role,   # "user" or "admin"
            "text": text,
            "ts": int(time.time())
        })
        save_users(users)


def track_message(key: str, chat_id: int, msg_id: int):
    """Register a message for potential auto-deletion."""
    _pending_deletes[key] = {
        "chat_id": chat_id,
        "msg_id": msg_id,
        "ts": time.time()
    }


def get_pending_deletes() -> dict:
    """Return all pending delete entries."""
    return _pending_deletes.copy()


def remove_pending(key: str):
    """Remove a message from pending deletes."""
    _pending_deletes.pop(key, None)


def map_admin_msg(admin_msg_id: int, user_id: int):
    """Map an admin-side forwarded message ID back to the source user."""
    _admin_msg_to_user[admin_msg_id] = user_id
    _user_to_admin_msg[user_id] = admin_msg_id


def get_user_from_admin_msg(admin_msg_id: int) -> int | None:
    """Get user_id from the admin message they're replying to."""
    return _admin_msg_to_user.get(admin_msg_id)


def store_msg_id_for_user(user_id: int, chat_id: int, msg_id: int):
    """Store a message ID in the user's record (for /deletechat)."""
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["msg_ids"].append({"chat_id": chat_id, "msg_id": msg_id})
        save_users(users)


def clear_user_msgs(user_id: int):
    """Clear all stored message IDs for a user (after /deletechat)."""
    users = load_users()
    uid = str(user_id)
    if uid in users:
        users[uid]["msg_ids"] = []
        users[uid]["history"] = []
        users[uid]["log_msg_id"] = None
        save_users(users)


def get_all_users() -> dict:
    """Return all users."""
    return load_users()
