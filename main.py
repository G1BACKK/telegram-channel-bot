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
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8230499628:AAGlmcytWoLeF5c8fKg_UL2BNLSjMCEJHiQ')
CHANNEL_ID = os.environ.get('CHANNEL_ID')
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', 'https://telegram-channel-bot-ah15.onrender.com')

# Log configuration details
logger.info(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")  # Log first 10 chars for security
logger.info(f"CHANNEL_ID: {CHANNEL_ID}")
logger.info(f"RENDER_URL: {RENDER_URL}")

if not BOT_TOKEN or not CHANNEL_ID:
    logger.error("❌ Missing BOT_TOKEN or CHANNEL_ID environment variables")
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
    logger.info(f"Received /start command from {message.chat.id}")
    bot.reply_to(message,
        "👋 Hello! I'm your channel member manager.\n\n"
        "I track when members join your channel.\n\n"
        "To remove members who joined at a specific time:\n"
        "/remove YYYY-MM-DD HH:MM:SS\n\n"
        "Example:\n"
        "/remove 2023-08-01 14:30:00\n\n"
        "Debug commands:\n"
        "/debug - Show debug information\n"
        "/status - Show tracked members"
    )

@bot.message_handler(commands=['debug'])
def debug_info(message):
    """Show debug information"""
    debug_text = (
        f"🤖 Bot Debug Information:\n\n"
        f"Channel ID: {CHANNEL_ID}\n"
        f"Tracked members: {len(member_join_times)}\n"
        f"Server time: {datetime.now(pytz.UTC)}\n"
        f"Webhook URL: {RENDER_URL}/webhook\n\n"
        f"To test, add a user to your channel and then use /status"
    )
    bot.reply_to(message, debug_text)
    logger.info(f"Sent debug info to {message.chat.id}")

@bot.message_handler(commands=['status'])
def show_status(message):
    """Show how many members are being tracked"""
    tracked_count = len([uid for uid in member_join_times.keys() if not isinstance(uid, str)])
    
    status_text = (
        f"📊 Bot Status:\n\n"
        f"Currently tracking: {tracked_count} members\n"
        f"Channel ID: {CHANNEL_ID}\n\n"
    )
    
    if tracked_count > 0:
        status_text += "Tracked members (last 5):\n"
        count = 0
        for user_id, join_time in list(member_join_times.items())[-5:]:
            if not isinstance(join_time, datetime):
                continue
            status_text += f"• User {user_id} at {join_time}\n"
            count += 1
            if count >= 5:
                break
    
    bot.reply_to(message, status_text)
    logger.info(f"Sent status to {message.chat.id}: Tracking {tracked_count} members")

@bot.message_handler(commands=['remove'])
def remove_members(message):
    try:
        logger.info(f"Received /remove command from {message.chat.id}")
        
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
        
        # 5-minute window around target time (wider for testing)
        start_time = target_time - timedelta(minutes=5)
        end_time = target_time + timedelta(minutes=5)
        
        # Find and remove users
        removed_count = 0
        users_to_remove = []
        
        for user_id, join_time in list(member_join_times.items()):
            if not isinstance(join_time, datetime):
                continue
                
            if start_time <= join_time <= end_time:
                users_to_remove.append(user_id)
        
        # Remove users from channel
        for user_id in users_to_remove:
            try:
                logger.info(f"Attempting to remove user {user_id}")
                bot.ban_chat_member(CHANNEL_ID, user_id, until_date=datetime.now() + timedelta(seconds=30))
                removed_count += 1
                del member_join_times[user_id]
                logger.info(f"Successfully removed user {user_id}")
            except Exception as e:
                logger.error(f"Failed to remove user {user_id}: {e}")
        
        bot.reply_to(message, f"✅ Removed {removed_count} members who joined around {target_time}")
        logger.info(f"Removed {removed_count} members for {message.chat.id}")
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid time format. Please use: YYYY-MM-DD HH:MM:SS")
    except Exception as e:
        logger.error(f"Error in remove_members: {e}")
        bot.reply_to(message, f"❌ Error: {e}")

@bot.chat_member_handler()
def track_new_members(chat_member_updated):
    """Track when new members join the channel"""
    try:
        logger.info(f"Received chat member update for chat: {chat_member_updated.chat.id}")
        logger.info(f"Expected Channel ID: {CHANNEL_ID}")
        
        if str(chat_member_updated.chat.id) != str(CHANNEL_ID):
            logger.info(f"Ignoring update from chat {chat_member_updated.chat.id} (not target channel)")
            return
            
        user = chat_member_updated.new_chat_member.user
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status
        
        logger.info(f"User {user.id} status changed: {old_status} -> {new_status}")
        
        if (old_status in ['left', 'kicked', 'restricted'] and 
            new_status in ['member', 'administrator', 'creator']):
            
            join_time = datetime.now(pytz.UTC)
            member_join_times[user.id] = join_time
            logger.info(f"✅ Tracking new user {user.id} joined at {join_time}")
            
    except Exception as e:
        logger.error(f"Error in track_new_members: {e}")

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
