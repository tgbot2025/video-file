# tg_bot.py
import os
import telebot
import threading
import time
import traceback

# ========== CONFIG - edit these before pushing ==========
# BOT_TOKEN should be set as environment variable (Render) or set locally for testing.
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set. Set BOT_TOKEN before running.")

CHANNEL_USERNAME = "@ViralCityBD"   # change if different
ADMIN_ID = 6705245237               # your numeric Telegram ID
UPDATE_CHANNEL_URL = "https://t.me/+inmCyx05zdMyNTll"
VIDEO_STORE_FILE = "current_video.txt"  # persistent file for file_id
DELETE_AFTER = 900  # seconds = 15 minutes
# =======================================================

bot = telebot.TeleBot(BOT_TOKEN)


# ---------- persistence ----------
def save_file_id(file_id: str):
    try:
        with open(VIDEO_STORE_FILE, "w", encoding="utf-8") as f:
            f.write(file_id)
    except Exception:
        traceback.print_exc()


def load_file_id():
    try:
        if os.path.exists(VIDEO_STORE_FILE):
            with open(VIDEO_STORE_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                return data if data else None
    except Exception:
        traceback.print_exc()
    return None


# ---------- delete helper (per-user only) ----------
def schedule_delete(chat_id: int, *message_ids):
    def _del():
        time.sleep(DELETE_AFTER)
        for mid in message_ids:
            try:
                bot.delete_message(chat_id, mid)
            except Exception:
                pass
    threading.Thread(target=_del, daemon=True).start()


# ---------- join prompt ----------
def send_join_prompt(chat_id):
    markup = telebot.types.InlineKeyboardMarkup()
    join_btn = telebot.types.InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")
    try_btn = telebot.types.InlineKeyboardButton("✅ Try Again", callback_data="check_join")
    # put join button full width then try again (2 rows)
    markup.add(join_btn)
    markup.add(try_btn)
    bot.send_message(chat_id, "👋 Please join my update channel to use me!", reply_markup=markup)


# ---------- /start ----------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    current_file_id = load_file_id()

    try:
        # check membership (bot must be admin in channel for reliable result)
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        status = getattr(member, "status", None)
        if status in ("member", "creator", "administrator"):
            if not current_file_id:
                bot.send_message(chat_id, "🚫 Currently no video available. Admin can set one with /update.")
                return

            # send video (file_id) to this user
            sent_vid = bot.send_video(chat_id, current_file_id)

            # send separate styled notice message + update channel button
            notice_text = (
                "⚠️ *Important:*\n"
                "All Messages will be deleted after *15 minutes*.\n\n"
                "Please save or forward these messages to your *personal saved messages* to avoid losing them!"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("📢 UPDATE CHANNEL", url=UPDATE_CHANNEL_URL))

            sent_notice = bot.send_message(chat_id, notice_text, parse_mode="Markdown", reply_markup=markup)

            # schedule deletion of both messages for this user only
            schedule_delete(chat_id, sent_vid.message_id, sent_notice.message_id)

        else:
            send_join_prompt(chat_id)

    except Exception as e:
        # if any error (e.g., bot not admin in channel), fallback to join prompt
        print("get_chat_member error:", e)
        send_join_prompt(chat_id)


# ---------- callback for Try Again ----------
@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
    try:
        bot.answer_callback_query(call.id, "Checking membership...")
    except Exception:
        pass
    time.sleep(2)  # give Telegram a moment if user just joined
    cmd_start(call.message)


# ---------- /update (admin only) ----------
@bot.message_handler(commands=['update'])
def cmd_update(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔️ তুমি অ্যাডমিন নও।")
        return

    bot.send_message(message.chat.id, "📤 এখন ভিডিও পাঠাও (এই চ্যাটে)।")
    bot.register_next_step_handler(message, save_video)


def save_video(message):
    if message.video:
        file_id = message.video.file_id
        save_file_id(file_id)
        bot.reply_to(message, "✅ ভিডিও সফলভাবে আপডেট ও সংরক্ষিত হয়েছে!")
    else:
        bot.reply_to(message, "❌ দয়া করে একটি ভিডিও ফাইল পাঠাও।")
