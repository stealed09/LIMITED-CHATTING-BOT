"""
admin.py - Handles admin's reply messages.
When admin replies to a forwarded message, bot routes reply back to the user.
"""

import telebot
from telebot.types import Message

from config import load_config
from storage import (
    get_user_from_admin_msg, get_user,
    append_history, store_msg_id_for_user
)
from utils.log_channel import update_log
from utils.autodelete import schedule_delete


def register_admin_handlers(bot: telebot.TeleBot):

    @bot.message_handler(
        func=lambda m: True,
        content_types=["text", "photo", "video", "voice", "document", "audio"]
    )
    def handle_admin_reply(msg: Message):
        config = load_config()
        admin_id = config["admin_id"]

        # Only process messages from admin
        if msg.from_user.id != admin_id:
            return

        # Must be a reply to route to user
        if not msg.reply_to_message:
            return  # Not a reply — let commands.py handle or ignore

        replied_msg_id = msg.reply_to_message.message_id
        target_user_id = get_user_from_admin_msg(replied_msg_id)

        if not target_user_id:
            # Could be admin replying to something else
            return

        # Check if user is blocked
        if target_user_id in config.get("blocked_users", []):
            bot.send_message(admin_id, "🚫 This user is blocked. Unblock first with /unblock")
            return

        content_type = msg.content_type
        log_text = ""

        try:
            if content_type == "text":
                log_text = msg.text or ""
                sent = bot.send_message(
                    target_user_id,
                    f"💬 <b>Support reply:</b>\n\n{msg.text}",
                    parse_mode="HTML"
                )
            elif content_type == "photo":
                log_text = "📷 Photo reply" + (f": {msg.caption}" if msg.caption else "")
                sent = bot.send_photo(
                    target_user_id,
                    msg.photo[-1].file_id,
                    caption=f"💬 <b>Support:</b>\n{msg.caption or ''}",
                    parse_mode="HTML"
                )
            elif content_type == "video":
                log_text = "🎥 Video reply"
                sent = bot.send_video(
                    target_user_id,
                    msg.video.file_id,
                    caption=f"💬 <b>Support:</b>\n{msg.caption or ''}",
                    parse_mode="HTML"
                )
            elif content_type == "voice":
                log_text = "🎤 Voice reply"
                sent = bot.send_voice(
                    target_user_id,
                    msg.voice.file_id
                )
            elif content_type == "document":
                log_text = f"📎 Document reply: {msg.document.file_name or 'file'}"
                sent = bot.send_document(
                    target_user_id,
                    msg.document.file_id,
                    caption=f"💬 <b>Support:</b> {msg.caption or ''}",
                    parse_mode="HTML"
                )
            elif content_type == "audio":
                log_text = "🎵 Audio reply"
                sent = bot.send_audio(
                    target_user_id,
                    msg.audio.file_id
                )
            else:
                bot.send_message(admin_id, f"⚠️ Unsupported reply type: {content_type}")
                return

        except telebot.apihelper.ApiTelegramException as e:
            if "bot was blocked by the user" in str(e).lower():
                bot.send_message(admin_id, f"❌ User <code>{target_user_id}</code> has blocked the bot.", parse_mode="HTML")
            else:
                bot.send_message(admin_id, f"❌ Error sending reply: {e}")
            return

        # Confirm to admin
        confirm = bot.send_message(admin_id, "✅ <i>Reply sent!</i>", parse_mode="HTML")

        # Store message IDs
        store_msg_id_for_user(target_user_id, target_user_id, sent.message_id)
        store_msg_id_for_user(target_user_id, admin_id, msg.message_id)

        # Update history and log channel
        append_history(target_user_id, "admin", log_text)
        user_data = get_user(target_user_id)
        if user_data:
            update_log(bot, config, user_data)

        # Auto-delete schedule
        secs = config.get("autodelete_seconds", 0)
        per_user = config.get("per_user_autodelete", {})
        if str(target_user_id) in per_user:
            secs = per_user[str(target_user_id)]

        if secs > 0:
            schedule_delete(f"areply_{target_user_id}_{msg.message_id}", admin_id, msg.message_id, secs)
            schedule_delete(f"ureply_{target_user_id}_{sent.message_id}", target_user_id, sent.message_id, secs)
