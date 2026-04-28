"""
antispam.py - Rate limiting: max 1 message per 5 seconds per user.
Uses in-memory timestamp tracking.
"""

import time

_last_msg_time: dict = {}   # user_id -> last timestamp
SPAM_INTERVAL = 5           # seconds between allowed messages


def is_spam(user_id: int) -> bool:
    """Returns True if user is sending too fast."""
    now = time.time()
    last = _last_msg_time.get(user_id, 0)
    if now - last < SPAM_INTERVAL:
        return True
    _last_msg_time[user_id] = now
    return False


def reset_user(user_id: int):
    """Reset spam timer for a user (e.g., after unblock)."""
    _last_msg_time.pop(user_id, None)
