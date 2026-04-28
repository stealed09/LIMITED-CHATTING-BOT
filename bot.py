"""
bot.py - Main entry point.
"""

import os
import sys
import time
import telebot

from config import load_config, save_config
from storage import load_users
from utils.autodelete import start_autodelete_worker
from handlers.commands import register_commands, register_callbacks
from handlers.user import register_user_handlers
from handlers.admin import register_admin_handlers


def setup_config() -> dict:
    config = load_config()
    env_token = os.environ.get("BOT_TOKEN", "")
    env_admin = os.environ.get("ADMIN_ID", "")
    if env_token:
        config["bot_token"] = env_token
    if env_admin:
        try:
            config["admin_id"] = int(env_admin)
        except ValueError:
            pass
    if not config.get("bot_token"):
        print("❌ ERROR: No bot token set.")
        print("Set BOT_TOKEN env variable or add to config.json")
        sys.exit(1)
    if not config.get("admin_id"):
        print("❌ ERROR: No admin_id set.")
        print("Set ADMIN_ID env variable or add to config.json")
        sys.exit(1)
    save_config(config)
    return config


def main():
    config = setup_config()
    token = config["bot_token"]
    admin_id = config["admin_id"]

    print(f"🤖 Starting bot...")
    print(f"👑 Admin ID: {admin_id}")
    print(f"👥 Loaded {len(load_users())} users from storage")

    bot = telebot.TeleBot(token, parse_mode=None)

    # ✅ CORRECT ORDER: commands → callbacks → users → admin
    register_commands(bot)
    register_callbacks(bot)
    register_user_handlers(bot)   # users first
    register_admin_handlers(bot)  # admin replies second

    start_autodelete_worker(bot)

    try:
        bot.send_message(
            admin_id,
            "✅ <b>Bot started successfully!</b>\n\n"
            f"📊 Users in DB: {len(load_users())}\n"
            f"⏱ Auto-delete: {config.get('autodelete_mode', 'off')}\n"
            f"📋 Log channel: {'✅' if config.get('log_channel_id') else '❌ not set'}\n\n"
            "Send /start to see all commands.",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"[STARTUP] Could not notify admin: {e}")
        print("👆 Fix: Open the bot in Telegram and send /start from your admin account first!")

    print("✅ Bot is running. Press Ctrl+C to stop.")

    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=15, logger_level=None)
        except Exception as e:
            print(f"[POLLING ERROR] {e}")
            print("Restarting in 5 seconds...")
            time.sleep(5)


if __name__ == "__main__":
    main()
