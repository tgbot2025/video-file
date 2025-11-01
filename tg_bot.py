# tg_bot.py
import os
import telebot
import threading
import time
import traceback

# ========== CONFIG (Change only if needed) ==========
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set this in Render env vars
CHANNEL_USERNAME = "@ViralCityBD"   # the channel to check membership
ADMIN_ID = 6705245237               # your telegram numeric ID (you are admin)
UPDATE_CHANNEL_URL = "https://t.me/+inmCyx05zdMyNTll"
VIDEO_STORE_FILE = "current_video.txt"  # persistent storage for file_id
DELETE_AFTER = 900  # seconds (15 minutes)
# ====================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is not set. Set BOT_TOKEN before running.")

bot = telebot.TeleBot(BOT_TOKEN)


# ---------- helpers: persist video file_id ----------
def save_video_file_id(file_id: str):
    try:
        with open(VIDEO_STORE_FILE, "w", encoding="utf-8") as f:
            f.write(file_id)
    except Exception:
        traceback.print_exc()


def load_video_file_id():
    try:
        if os.path.exists(VIDEO_STORE_FILE):
            with open(VIDEO_STORE_FILE, "r", encoding="utf-8") as f:
                data = f.read().strip()
                return data if data else None
    except Exception:
        traceback.print_exc()
    return None


# ---------- helper: delete messages after delay ----------
def schedule_delete(chat_id: int, *message_ids):
    def _del():
        time.sleep(DELETE_AFTER)
        for mid in message_ids:
            try:
                bot.delete_message(chat_id, mid)
            except Exception:
                pass
    threading.Thread(target=_del, daemon=True).start()


# ---------- helper: join prompt ----------
def send_join_prompt(chat_id: int):
    markup = telebot.types.InlineKeyboardMarkup()
    # Join Channel button (text "Join Channel")
    join_btn = telebot.types.InlineKeyboardButton("🔗 Join Channel", url=f"https://t.me/{CHANNEL_USERNAME.lstrip('@')}")
    try_again = telebot.types.InlineKeyboardButton("✅ Try Again", callback_data="check_join")
    markup.add(join_btn)
    markup.add(try_again)
    bot.send_message(chat_id, "👋 Please join my update channel to use me!", reply_markup=markup)


# ---------- /start handler ----------
@bot.message_handler(commands=['start'])
def cmd_start(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    current_video = load_video_file_id()

    try:
        # check membership; NOTE: bot must be admin in the channel for reliable results
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        status = getattr(member, "status", None)
        if status in ("member", "creator", "administrator"):
            # allowed -> send video + separate info message + update channel button
            if not current_video:
                bot.send_message(chat_id, "🚫 Currently no video available. Admin can set one with /update.")
                return

            # send video (without caption)
            sent_vid = bot.send_video(chat_id, current_video)

            # send the important notice as a separate message (styled)
            notice_text = (
                "⚠️ *Important:*\n"
                "All Messages will be deleted after *15 minutes*.\n\n"
                "Please save or forward these messages to your *personal saved messages* to avoid losing them!"
            )
            markup = telebot.types.InlineKeyboardMarkup()
            markup.add(telebot.types.InlineKeyboardButton("📢 UPDATE CHANNEL", url=UPDATE_CHANNEL_URL))

            sent_notice = bot.send_message(chat_id, notice_text, parse_mode="Markdown", reply_markup=markup)

            # schedule deletion of both messages after DELETE_AFTER seconds
            schedule_delete(chat_id, sent_vid.message_id, sent_notice.message_id)

        else:
            # not a member
            send_join_prompt(chat_id)

    except Exception as e:
        # fallback to join prompt on any error (e.g., bot not admin in channel)
        # log for debugging
        print("get_chat_member error:", e)
        send_join_prompt(chat_id)


# ---------- callback: Try Again ----------
@bot.callback_query_handler(func=lambda call: call.data == "check_join")
def callback_check_join(call):
    # short delay to allow telegram to update membership after user joined
    try:
        bot.answer_callback_query(call.id, "Checking membership...")
    except Exception:
        pass
    time.sleep(2)
    # re-run start logic
    cmd_start(call.message)


# ---------- /update handler (admin only) ----------
@bot.message_handler(commands=['update'])
def cmd_update(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "⛔️ You are not authorized to update videos.")
        return

    bot.send_message(message.chat.id, "📤 Please send the new video file (or forward one) now. It will replace the current video.")
    # register next step to accept the video
    bot.register_next_step_handler(message, receive_video_for_update)


def receive_video_for_update(message):
    if message.video:
        file_id = message.video.file_id
        save_video_file_id(file_id)
        bot.send_message(message.chat.id, "✅ Video updated and saved successfully!")
    else:
        bot.send_message(message.chat.id, "❌ No video detected. Please send a video file.")


# ---------- start polling ----------
if __name__ == "__main__":
    print("✅ tg_bot is starting...")
    # load once to ensure file exists / readable
    _ = load_video_file_id()
    # poll with some timeout to reduce read timeouts
    bot.polling(none_stop=True, interval=5, timeout=60)
