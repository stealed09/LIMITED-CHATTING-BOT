"""
autodelete.py - Background auto-delete scheduler.
Runs in a thread, checks every 2 seconds, deletes or hides expired messages.
"""

import time
import threading
import telebot
from storage import get_pending_deletes, remove_pending
from config import load_config


def _delete_worker(bot: telebot.TeleBot):
    """Background thread: periodically checks and deletes expired messages."""
    while True:
        try:
            config = load_config()
            mode = config.get("autodelete_type", "full")
            pending = get_pending_deletes()
            now = time.time()

            for key, entry in pending.items():
                chat_id = entry["chat_id"]
                msg_id = entry["msg_id"]
                ts = entry["ts"]
                seconds = entry.get("seconds", 0)

                if seconds <= 0:
                    continue

                if now - ts >= seconds:
                    try:
                        if mode == "full":
                            bot.delete_message(chat_id, msg_id)
                        elif mode == "hide":
                            bot.edit_message_text(
                                "⚠️ <i>Message auto-deleted</i>",
                                chat_id=chat_id,
                                message_id=msg_id,
                                parse_mode="HTML"
                            )
                        elif mode == "admin_only":
                            # Only delete if chat_id matches admin
                            admin_id = config.get("admin_id")
                            if chat_id == admin_id:
                                bot.delete_message(chat_id, msg_id)
                    except Exception as e:
                        if "message to delete not found" not in str(e).lower():
                            print(f"[AUTODELETE] Error deleting {key}: {e}")
                    remove_pending(key)

        except Exception as e:
            print(f"[AUTODELETE WORKER] Error: {e}")

        time.sleep(2)


def start_autodelete_worker(bot: telebot.TeleBot):
    """Start the background auto-delete thread (daemon)."""
    t = threading.Thread(target=_delete_worker, args=(bot,), daemon=True)
    t.start()
    print("[AUTODELETE] Background worker started.")


def schedule_delete(key: str, chat_id: int, msg_id: int, seconds: int):
    """Register a message for auto-deletion after `seconds` seconds."""
    from storage import _pending_deletes
    import time
    _pending_deletes[key] = {
        "chat_id": chat_id,
        "msg_id": msg_id,
        "ts": time.time(),
        "seconds": seconds
    }
