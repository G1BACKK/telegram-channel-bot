import os
import logging
from datetime import datetime, timedelta
from flask import Flask, request
import telebot
import pytz

# Initialize Flask app
app = Flask(__name__)

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-channel-bot-ah15.onrender.com')

if not BOT_TOKEN or not CHANNEL_ID:
    logger.error("Missing BOT_TOKEN or CHANNEL_ID environment variables")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Store member join times
member_join_times = {}

@app.route('/')
def index():
    return '🤖 Bot is running! Use Telegram to interact with me.'

@app.route('/webhook', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    return 'Forbidden', 403

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,
        "👋 Hello! I'm your channel member manager.\n\n"
        "I track when members join your channel.\n\n"
        "To remove members who joined at a specific time:\n"
        "/remove YYYY-MM-DD HH:MM:SS\n\n"
        "Example:\n"
        "/remove 2023-08-01 14:30:00\n\n"
        "Check status:\n"
        "/status"
    )

@bot.message_handler(commands=['remove'])
def remove_members(message):
    try:
        if message.chat.type != 'private':
            bot.reply_to(message, "Please use this command in a private chat with me.")
            return
            
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message,
                "Please specify a time:\n"
                "/remove YYYY-MM-DD HH:MM:SS\n\n"
                "Example:\n"
                "/remove 2023-08-01 14:30:00"
            )
            return
            
        # Parse time
        time_parts = args[1:]
        if len(time_parts) == 1:
            time_str = time_parts[0] + " 00:00:00"
        else:
            time_str = ' '.join(time_parts[0:2])
            
        target_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
        
        # 2-minute window around target time
        start_time = target_time - timedelta(minutes=2)
        end_time = target_time + timedelta(minutes=2)
        
        # Find and remove users
        removed_count = 0
        
        for user_id, join_time in list(member_join_times.items()):
            if not isinstance(join_time, datetime):
                continue
                
            if start_time <= join_time <= end_time:
                try:
                    bot.ban_chat_member(CHANNEL_ID, user_id, until_date=datetime.now() + timedelta(seconds=30))
                    removed_count += 1
                    del member_join_times[user_id]
                except Exception as e:
                    logger.error(f"Failed to remove user {user_id}: {e}")
        
        bot.reply_to(message, f"✅ Removed {removed_count} members who joined around {target_time}")
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid time format. Please use: YYYY-MM-DD HH:MM:SS")
    except Exception as e:
        logger.error(f"Error in remove_members: {e}")
        bot.reply_to(message, "❌ An error occurred. Please try again.")

@bot.chat_member_handler()
def track_new_members(chat_member_updated):
    """Track when new members join the channel"""
    try:
        if str(chat_member_updated.chat.id) != str(CHANNEL_ID):
            return
            
        user = chat_member_updated.new_chat_member.user
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status
        
        if (old_status in ['left', 'kicked', 'restricted'] and 
            new_status in ['member', 'administrator', 'creator']):
            
            join_time = datetime.now(pytz.UTC)
            member_join_times[user.id] = join_time
            logger.info(f"User {user.id} joined at {join_time}")
            
    except Exception as e:
        logger.error(f"Error tracking member: {e}")

@bot.message_handler(commands=['status'])
def show_status(message):
    """Show how many members are being tracked"""
    tracked_count = len([uid for uid in member_join_times.keys() if not isinstance(uid, str)])
    bot.reply_to(message, f"📊 Currently tracking {tracked_count} channel members")

def set_webhook():
    """Set webhook for the bot"""
    try:
        webhook_url = f"{RENDER_URL}/webhook"
        bot.remove_webhook()
        success = bot.set_webhook(url=webhook_url)
        if success:
            logger.info(f"✅ Webhook set to: {webhook_url}")
            return True
        else:
            logger.error("❌ Failed to set webhook")
            return False
    except Exception as e:
        logger.error(f"Error setting webhook: {e}")
        return False

# Set webhook when the app starts
with app.app_context():
    if set_webhook():
        logger.info("✅ Webhook configured successfully")
    else:
        logger.error("❌ Webhook configuration failed")

if __name__ == '__main__':
    logger.info("🚀 Starting bot with webhooks...")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
