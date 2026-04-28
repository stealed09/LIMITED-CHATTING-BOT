"""
commands.py - Admin command handlers:
/start, /stats, /broadcast, /block, /unblock, /ban,
/setlogchannel, /setchannel, /setgroup,
/autodelete, /deletechat
"""

import time
import telebot
from telebot.types import Message

from config import load_config, save_config, parse_time_string
from storage import (
    get_all_users, get_user, upsert_user,
    clear_user_msgs, store_msg_id_for_user,
    append_history
)
from utils.log_channel import update_log


def register_commands(bot: telebot.TeleBot):

    # ─── /start ──────────────────────────────────────────────
    @bot.message_handler(commands=["start"])
    def cmd_start(msg: Message):
        config = load_config()
        uid = msg.from_user.id

        if uid == config["admin_id"]:
            bot.send_message(uid,
                "🛡️ <b>Admin Panel Active</b>\n\n"
                "<b>Commands:</b>\n"
                "/stats — User statistics\n"
                "/broadcast — Send to all users\n"
                "/block [id] — Block user\n"
                "/unblock [id] — Unblock user\n"
                "/autodelete [time] — Set auto-delete\n"
                "/deletechat [id] — Delete user chat\n"
                "/setlogchannel — Set log channel\n"
                "/setchannel — Set force-join channel\n"
                "/setgroup — Set force-join group\n",
                parse_mode="HTML"
            )
        else:
            name = msg.from_user.full_name
            username = msg.from_user.username
            upsert_user(uid, name, username)
            bot.send_message(uid,
                "👋 <b>Hello!</b> Send me a message and our support team will reply soon.\n\n"
                "⚡ Powered by Advanced Support Bot",
                parse_mode="HTML"
            )

    # ─── /stats ──────────────────────────────────────────────
    @bot.message_handler(commands=["stats"])
    def cmd_stats(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return

        users = get_all_users()
        total = len(users)
        blocked = len(config.get("blocked_users", []))
        active = total - blocked

        text = (
            "📊 <b>Bot Statistics</b>\n\n"
            f"👥 Total Users: <b>{total}</b>\n"
            f"✅ Active: <b>{active}</b>\n"
            f"🚫 Blocked: <b>{blocked}</b>\n\n"
            f"📋 Log Channel: {'✅ Set' if config.get('log_channel_id') else '❌ Not Set'}\n"
            f"🔒 Force Channel: {'✅ Set' if config.get('force_channel') else '❌ Not set'}\n"
            f"⏱ Auto-Delete: <b>{config.get('autodelete_mode', 'off')}</b>"
        )
        bot.send_message(msg.chat.id, text, parse_mode="HTML")

    # ─── /broadcast ──────────────────────────────────────────
    @bot.message_handler(commands=["broadcast"])
    def cmd_broadcast_start(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        sent = bot.send_message(msg.chat.id,
            "📢 <b>Broadcast Mode</b>\n\nReply to this message with what you want to send to all users.",
            parse_mode="HTML"
        )
        # We'll handle the reply in admin.py via reply detection

    @bot.message_handler(commands=["broadcastnow"])
    def cmd_broadcastnow(msg: Message):
        """Broadcast a text message immediately. Usage: /broadcastnow Your message here"""
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        text_to_send = msg.text.replace("/broadcastnow", "").strip()
        if not text_to_send:
            bot.send_message(msg.chat.id, "❌ Usage: /broadcastnow Your message here")
            return

        users = get_all_users()
        blocked = config.get("blocked_users", [])
        success, fail = 0, 0
        for uid_str, udata in users.items():
            uid = int(uid_str)
            if uid in blocked or uid == config["admin_id"]:
                continue
            try:
                bot.send_message(uid,
                    f"📢 <b>Broadcast:</b>\n\n{text_to_send}",
                    parse_mode="HTML"
                )
                success += 1
            except Exception:
                fail += 1
        bot.send_message(msg.chat.id,
            f"📢 Broadcast done.\n✅ Sent: {success}\n❌ Failed: {fail}"
        )

    # ─── /block ───────────────────────────────────────────────
    @bot.message_handler(commands=["block"])
    def cmd_block(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "❌ Usage: /block [user_id]")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Invalid user ID.")
            return
        blocked = config.get("blocked_users", [])
        if target_id not in blocked:
            blocked.append(target_id)
            config["blocked_users"] = blocked
            save_config(config)
        bot.send_message(msg.chat.id, f"🚫 User <code>{target_id}</code> blocked.", parse_mode="HTML")

    # ─── /unblock ─────────────────────────────────────────────
    @bot.message_handler(commands=["unblock"])
    def cmd_unblock(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "❌ Usage: /unblock [user_id]")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Invalid user ID.")
            return
        blocked = config.get("blocked_users", [])
        if target_id in blocked:
            blocked.remove(target_id)
            config["blocked_users"] = blocked
            save_config(config)
            bot.send_message(msg.chat.id, f"✅ User <code>{target_id}</code> unblocked.", parse_mode="HTML")
        else:
            bot.send_message(msg.chat.id, "⚠️ User is not blocked.")

    # ─── /autodelete ──────────────────────────────────────────
    @bot.message_handler(commands=["autodelete"])
    def cmd_autodelete(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()

        # /autodelete user_id 5m  → per-user setting
        if len(parts) == 3:
            try:
                target_id = str(int(parts[1]))
                secs = parse_time_string(parts[2])
                if secs == -1:
                    config["per_user_autodelete"].pop(target_id, None)
                    save_config(config)
                    bot.send_message(msg.chat.id, f"✅ Auto-delete disabled for <code>{target_id}</code>.", parse_mode="HTML")
                elif secs > 0:
                    config["per_user_autodelete"][target_id] = secs
                    save_config(config)
                    bot.send_message(msg.chat.id, f"✅ Auto-delete set to <b>{parts[2]}</b> for user <code>{target_id}</code>.", parse_mode="HTML")
                else:
                    bot.send_message(msg.chat.id, "❌ Invalid time format. Use: 30s, 10m, 1h")
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Usage: /autodelete [user_id] [time]")
            return

        # /autodelete 10m  → global setting
        if len(parts) == 2:
            secs = parse_time_string(parts[1])
            if secs == -1:
                config["autodelete_mode"] = "off"
                config["autodelete_seconds"] = 0
                save_config(config)
                bot.send_message(msg.chat.id, "✅ Auto-delete <b>disabled</b>.", parse_mode="HTML")
            elif secs > 0:
                config["autodelete_mode"] = parts[1]
                config["autodelete_seconds"] = secs
                save_config(config)
                bot.send_message(msg.chat.id, f"✅ Auto-delete set to <b>{parts[1]}</b> globally.", parse_mode="HTML")
            else:
                bot.send_message(msg.chat.id, "❌ Invalid format. Try: /autodelete 30s | 10m | 1h | off")
            return

        # /autodelete  → show current setting + type menu
        markup = telebot.types.InlineKeyboardMarkup()
        markup.row(
            telebot.types.InlineKeyboardButton("Full Delete", callback_data="adtype_full"),
            telebot.types.InlineKeyboardButton("Hide Mode", callback_data="adtype_hide"),
            telebot.types.InlineKeyboardButton("Admin Only", callback_data="adtype_admin_only")
        )
        current = config.get("autodelete_mode", "off")
        cur_type = config.get("autodelete_type", "full")
        bot.send_message(msg.chat.id,
            f"⏱ <b>Auto-Delete Settings</b>\n\n"
            f"Current mode: <b>{current}</b>\n"
            f"Delete type: <b>{cur_type}</b>\n\n"
            f"<b>Usage:</b>\n"
            f"/autodelete off\n"
            f"/autodelete 30s\n"
            f"/autodelete 10m\n"
            f"/autodelete 1h\n"
            f"/autodelete [user_id] 5m\n\n"
            f"Select delete type:",
            reply_markup=markup,
            parse_mode="HTML"
        )

    # ─── /deletechat ──────────────────────────────────────────
    @bot.message_handler(commands=["deletechat"])
    def cmd_deletechat(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "❌ Usage: /deletechat [user_id]")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Invalid user ID.")
            return

        user_data = get_user(target_id)
        if not user_data:
            bot.send_message(msg.chat.id, "❌ User not found.")
            return

        deleted = 0
        for entry in user_data.get("msg_ids", []):
            try:
                bot.delete_message(entry["chat_id"], entry["msg_id"])
                deleted += 1
            except Exception:
                pass

        clear_user_msgs(target_id)
        bot.send_message(msg.chat.id,
            f"🗑 Cleared <b>{deleted}</b> messages for user <code>{target_id}</code>.",
            parse_mode="HTML"
        )

    # ─── /setlogchannel ───────────────────────────────────────
    @bot.message_handler(commands=["setlogchannel"])
    def cmd_setlogchannel(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id,
                "📋 <b>Set Log Channel</b>\n\n"
                "1. Add me as admin to your channel\n"
                "2. Forward a message from the channel here OR send:\n"
                "<code>/setlogchannel -100xxxxxxxxx</code>",
                parse_mode="HTML"
            )
            return
        try:
            channel_id = int(parts[1])
            config["log_channel_id"] = channel_id
            save_config(config)
            bot.send_message(msg.chat.id, f"✅ Log channel set to <code>{channel_id}</code>", parse_mode="HTML")
        except ValueError:
            bot.send_message(msg.chat.id, "❌ Invalid channel ID.")

    # ─── /setchannel ──────────────────────────────────────────
    @bot.message_handler(commands=["setchannel"])
    def cmd_setchannel(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "Usage: /setchannel -100xxxxxxxxx (or 'off' to disable)")
            return
        val = parts[1]
        if val.lower() == "off":
            config["force_channel"] = None
            save_config(config)
            bot.send_message(msg.chat.id, "✅ Force-join channel disabled.")
        else:
            try:
                config["force_channel"] = int(val)
                save_config(config)
                bot.send_message(msg.chat.id, f"✅ Force-join channel set to <code>{val}</code>", parse_mode="HTML")
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Invalid ID.")

    # ─── /setgroup ────────────────────────────────────────────
    @bot.message_handler(commands=["setgroup"])
    def cmd_setgroup(msg: Message):
        config = load_config()
        if msg.from_user.id != config["admin_id"]:
            return
        parts = msg.text.split()
        if len(parts) < 2:
            bot.send_message(msg.chat.id, "Usage: /setgroup -100xxxxxxxxx (or 'off' to disable)")
            return
        val = parts[1]
        if val.lower() == "off":
            config["force_group"] = None
            save_config(config)
            bot.send_message(msg.chat.id, "✅ Force-join group disabled.")
        else:
            try:
                config["force_group"] = int(val)
                save_config(config)
                bot.send_message(msg.chat.id, f"✅ Force-join group set to <code>{val}</code>", parse_mode="HTML")
            except ValueError:
                bot.send_message(msg.chat.id, "❌ Invalid ID.")


def register_callbacks(bot: telebot.TeleBot):
    """Register inline button callback handlers."""

    @bot.callback_query_handler(func=lambda c: c.data.startswith("adtype_"))
    def cb_adtype(call):
        config = load_config()
        if call.from_user.id != config["admin_id"]:
            bot.answer_callback_query(call.id, "Not authorized.")
            return
        atype = call.data.replace("adtype_", "")
        config["autodelete_type"] = atype
        save_config(config)
        bot.answer_callback_query(call.id, f"✅ Delete type set to: {atype}")
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)

    @bot.callback_query_handler(func=lambda c: c.data.startswith("block_"))
    def cb_block(call):
        config = load_config()
        if call.from_user.id != config["admin_id"]:
            bot.answer_callback_query(call.id, "Not authorized.")
            return
        target_id = int(call.data.replace("block_", ""))
        blocked = config.get("blocked_users", [])
        if target_id not in blocked:
            blocked.append(target_id)
            config["blocked_users"] = blocked
            save_config(config)
        bot.answer_callback_query(call.id, f"🚫 User {target_id} blocked!")
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    @bot.callback_query_handler(func=lambda c: c.data.startswith("delchat_"))
    def cb_delchat(call):
        config = load_config()
        if call.from_user.id != config["admin_id"]:
            bot.answer_callback_query(call.id, "Not authorized.")
            return
        target_id = int(call.data.replace("delchat_", ""))
        user_data = get_user(target_id)
        if not user_data:
            bot.answer_callback_query(call.id, "User not found.")
            return
        deleted = 0
        for entry in user_data.get("msg_ids", []):
            try:
                bot.delete_message(entry["chat_id"], entry["msg_id"])
                deleted += 1
            except Exception:
                pass
        clear_user_msgs(target_id)
        bot.answer_callback_query(call.id, f"🗑 Deleted {deleted} messages.")

    @bot.callback_query_handler(func=lambda c: c.data.startswith("reply_"))
    def cb_reply(call):
        config = load_config()
        if call.from_user.id != config["admin_id"]:
            bot.answer_callback_query(call.id, "Not authorized.")
            return
        target_id = int(call.data.replace("reply_", ""))
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id,
            f"✏️ Reply to user <code>{target_id}</code>:\n"
            f"<i>Just reply to any of their forwarded messages above.</i>",
            parse_mode="HTML"
          )
