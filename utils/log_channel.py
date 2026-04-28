"""
log_channel.py - Manages the one-message-per-user log channel system.
Each user gets exactly ONE message in the log channel, edited on every event.
"""

import time
import telebot
from storage import get_user, set_log_msg_id, append_history


def _format_log(user_data: dict) -> str:
    """Build the full log message text for a user."""
    name = user_data.get("name", "Unknown")
    username = user_data.get("username", "")
    user_id = user_data.get("user_id", "")
    history = user_data.get("history", [])

    uname_str = f"@{username}" if username else "no username"
    lines = [
        f"👤 <b>USER:</b> {name} ({uname_str})",
        f"🆔 <b>ID:</b> <code>{user_id}</code>",
        "",
        "━━━━━━━━━━━━━━━",
        ""
    ]

    for entry in history[-40:]:   # cap at 40 entries to avoid msg too long
        role = entry.get("role", "user")
        text = entry.get("text", "")
        ts = entry.get("ts", 0)
        time_str = time.strftime("%H:%M", time.localtime(ts)) if ts else ""

        if role == "user":
            lines.append(f"📩 [{time_str}] {text}")
        else:
            lines.append(f"🤖 [{time_str}] {text}")

    return "\n".join(lines)


def update_log(bot: telebot.TeleBot, config: dict, user_data: dict):
    """
    Create or edit the log channel message for a user.
    Uses user_data['log_msg_id'] to decide create vs edit.
    """
    log_channel = config.get("log_channel_id")
    if not log_channel:
        return

    text = _format_log(user_data)
    # Telegram max message length is 4096 chars
    if len(text) > 4000:
        text = text[-4000:]  # keep most recent content

    try:
        if not user_data.get("log_msg_id"):
            # First time — create message
            msg = bot.send_message(
                log_channel,
                text,
                parse_mode="HTML"
            )
            set_log_msg_id(user_data["user_id"], msg.message_id)
        else:
            # Edit existing message
            bot.edit_message_text(
                text,
                chat_id=log_channel,
                message_id=user_data["log_msg_id"],
                parse_mode="HTML"
            )
    except Exception as e:
        # Log channel message may be deleted or bot lacks permission
        if "message is not modified" not in str(e).lower():
            print(f"[LOG CHANNEL] Error: {e}")
            # If message was deleted externally, reset so it gets recreated
            if "message to edit not found" in str(e).lower():
                set_log_msg_id(user_data["user_id"], None)
