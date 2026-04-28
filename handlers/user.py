"""
user.py - Handles all messages coming FROM regular users.
Forwards them to admin with inline controls.
"""

import time
import telebot
from telebot.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import load_config
from storage import (
    upsert_user, get_user, append_history,
    map_admin_msg, store_msg_id_for_user
)
from utils.antispam import is_spam
from utils.log_channel import update_log
from utils.autodelete import schedule_delete


def _check_force_join(bot: telebot.TeleBot, config: dict, user_id: int) -> bool:
    """
    Returns True if user has joined required channel/group.
    Sends join prompt if not.
    """
    channel = config.get("force_channel")
    group = config.get("force_group")
    missing = []

    if channel:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status in ("left", "kicked"):
                missing.append(("channel", channel))
        except Exception:
            pass  # Can't check → let through

    if group:
        try:
            member = bot.get_chat_member(group, user_id)
            if member.status in ("left", "kicked"):
                missing.append(("group", group))
        except Exception:
            pass

    if missing:
        markup = InlineKeyboardMarkup()
        for kind, chat_id in missing:
            try:
                chat = bot.get_chat(chat_id)
                invite = chat.invite_link or f"https://t.me/c/{str(chat_id).replace('-100', '')}"
                markup.add(InlineKeyboardButton(
                    f"{'📢 Join Channel' if kind == 'channel' else '👥 Join Group'}",
                    url=invite
                ))
            except Exception:
                pass
        markup.add(InlineKeyboardButton("✅ I Joined", callback_data="check_join"))
        bot.send_message(user_id,
            "🔒 <b>Access Required</b>\n\nPlease join our channel/group to use this bot.",
            reply_markup=markup,
            parse_mode="HTML"
        )
        return False
    return True


def _get_autodelete_seconds(config: dict, user_id: int) -> int:
    """Get effective auto-delete seconds for a user (per-user overrides global)."""
    per_user = config.get("per_user_autodelete", {})
    if str(user_id) in per_user:
        return per_user[str(user_id)]
    return config.get("autodelete_seconds", 0)


def _build_admin_markup(user_id: int) -> InlineKeyboardMarkup:
    """Build inline buttons for admin message."""
    markup = InlineKeyboardMarkup()
    markup.row(
        InlineKeyboardButton("↩️ Reply", callback_data=f"reply_{user_id}"),
        InlineKeyboardButton("🚫 Block", callback_data=f"block_{user_id}"),
        InlineKeyboardButton("🗑 Del Chat", callback_data=f"delchat_{user_id}")
    )
    return markup


def register_user_handlers(bot: telebot.TeleBot):

    # ─── Force-join check callback ────────────────────────────
    @bot.callback_query_handler(func=lambda c: c.data == "check_join")
    def cb_check_join(call):
        config = load_config()
        uid = call.from_user.id
        if _check_force_join(bot, config, uid):
            bot.answer_callback_query(call.id, "✅ Access granted!")
            bot.send_message(uid,
                "✅ <b>Access granted!</b> You can now send messages.",
                parse_mode="HTML"
            )
        else:
            bot.answer_callback_query(call.id, "❌ You haven't joined yet.")

    # ─── Text messages from users ─────────────────────────────
    @bot.message_handler(
        func=lambda m: True,
        content_types=["text", "photo", "video", "voice", "document", "audio", "sticker"]
    )
    def handle_user_message(msg: Message):
        config = load_config()
        uid = msg.from_user.id
        admin_id = config["admin_id"]

        # Skip if admin is talking (handled in admin.py)
        if uid == admin_id:
            return

        # Block check
        if uid in config.get("blocked_users", []):
            bot.send_message(uid, "🚫 You have been blocked from using this bot.")
            return

        # Force join check
        if not _check_force_join(bot, config, uid):
            return

        # Anti-spam check
        if is_spam(uid):
            bot.send_message(uid,
                "⚠️ <b>Slow down!</b> Please wait a few seconds before sending another message.",
                parse_mode="HTML"
            )
            return

        # Upsert user record
        name = msg.from_user.full_name
        username = msg.from_user.username
        user_data = upsert_user(uid, name, username)

        # Build header for admin
        uname_str = f"@{username}" if username else "no username"
        header = (
            f"👤 <b>{name}</b> ({uname_str})\n"
            f"🆔 <code>{uid}</code>\n"
            f"━━━━━━━━━━━━━━━\n"
        )

        # Determine content description for log
        content_type = msg.content_type
        log_text = ""

        try:
            # Forward message content to admin with header
            if content_type == "text":
                log_text = msg.text or ""
                admin_msg = bot.send_message(
                    admin_id,
                    header + f"📩 {msg.text}",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "photo":
                log_text = "📷 Photo" + (f": {msg.caption}" if msg.caption else "")
                admin_msg = bot.send_photo(
                    admin_id,
                    msg.photo[-1].file_id,
                    caption=header + f"📷 <b>Photo</b>" + (f"\n{msg.caption}" if msg.caption else ""),
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "video":
                log_text = "🎥 Video" + (f": {msg.caption}" if msg.caption else "")
                admin_msg = bot.send_video(
                    admin_id,
                    msg.video.file_id,
                    caption=header + f"🎥 <b>Video</b>" + (f"\n{msg.caption}" if msg.caption else ""),
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "voice":
                log_text = "🎤 Voice message"
                admin_msg = bot.send_voice(
                    admin_id,
                    msg.voice.file_id,
                    caption=header + "🎤 <b>Voice Message</b>",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "document":
                log_text = f"📎 Document: {msg.document.file_name or 'file'}"
                admin_msg = bot.send_document(
                    admin_id,
                    msg.document.file_id,
                    caption=header + f"📎 <b>Document:</b> {msg.document.file_name or 'file'}",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "audio":
                log_text = "🎵 Audio"
                admin_msg = bot.send_audio(
                    admin_id,
                    msg.audio.file_id,
                    caption=header + "🎵 <b>Audio</b>",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            elif content_type == "sticker":
                log_text = "🎭 Sticker"
                admin_msg = bot.send_sticker(admin_id, msg.sticker.file_id)
                # Send header separately for stickers
                admin_msg = bot.send_message(
                    admin_id,
                    header + "🎭 <b>Sticker</b>",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )
            else:
                log_text = f"[{content_type}]"
                admin_msg = bot.send_message(
                    admin_id,
                    header + f"[{content_type} message]",
                    parse_mode="HTML",
                    reply_markup=_build_admin_markup(uid)
                )

        except Exception as e:
            print(f"[USER HANDLER] Error forwarding to admin: {e}")
            return

        # Confirm receipt to user
        confirm = bot.send_message(uid,
            "✅ <i>Message sent. We'll reply soon!</i>",
            parse_mode="HTML"
        )

        # Map admin message → user for reply routing
        map_admin_msg(admin_msg.message_id, uid)

        # Store message IDs for /deletechat
        store_msg_id_for_user(uid, uid, msg.message_id)
        store_msg_id_for_user(uid, admin_id, admin_msg.message_id)

        # Append to history and update log channel
        append_history(uid, "user", log_text)
        # Reload user_data (now with updated history)
        user_data = get_user(uid)
        update_log(bot, config, user_data)

        # Schedule auto-delete if enabled
        secs = _get_autodelete_seconds(config, uid)
        if secs > 0:
            ts_key = f"user_{uid}_{msg.message_id}"
            schedule_delete(ts_key, uid, msg.message_id, secs)
            ts_key2 = f"admin_{uid}_{admin_msg.message_id}"
            schedule_delete(ts_key2, admin_id, admin_msg.message_id, secs)
            ts_key3 = f"confirm_{uid}_{confirm.message_id}"
            schedule_delete(ts_key3, uid, confirm.message_id, secs)
