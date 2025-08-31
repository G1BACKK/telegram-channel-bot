import os
import logging
import time
from datetime import datetime, timedelta
import telebot
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration - Set these in Render environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Store member join times
member_join_times = {}

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message,
        "👋 Hello! I'm your channel member manager.\n\n"
        "I track when members join your channel.\n\n"
        "To remove members who joined at a specific time:\n"
        "/remove YYYY-MM-DD HH:MM:SS\n\n"
        "Example:\n"
        "/remove 2023-08-01 14:30:00"
    )

@bot.message_handler(commands=['remove'])
def remove_members(message):
    try:
        # Check if command is sent in private chat
        if message.chat.type != 'private':
            bot.reply_to(message, "Please use this command in a private chat with me.")
            return
            
        # Parse command arguments
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message,
                "Please specify a time:\n"
                "/remove YYYY-MM-DD HH:MM:SS\n\n"
                "Example:\n"
                "/remove 2023-08-01 14:30:00"
            )
            return
            
        # Parse time (handle with/without time)
        time_parts = args[1:]
        if len(time_parts) == 1:
            # Only date provided, assume midnight
            time_str = time_parts[0] + " 00:00:00"
        else:
            # Date and time provided
            time_str = ' '.join(time_parts[0:2])
            
        target_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
        
        # 2-minute window around target time
        start_time = target_time - timedelta(minutes=2)
        end_time = target_time + timedelta(minutes=2)
        
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
                bot.ban_chat_member(
                    chat_id=CHANNEL_ID, 
                    user_id=user_id,
                    until_date=datetime.now() + timedelta(seconds=30)
                )
                removed_count += 1
                # Remove from tracking
                if user_id in member_join_times:
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
        # Only track members in our target channel
        if str(chat_member_updated.chat.id) != str(CHANNEL_ID):
            return
            
        user = chat_member_updated.new_chat_member.user
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status
        
        # Check if this is a new member joining
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

def start_bot():
    """Start the bot with error handling"""
    logger.info("Starting bot...")
    
    # Try to remove any existing webhook (just in case)
    try:
        bot.remove_webhook()
    except:
        pass
        
    # Start polling with error recovery
    while True:
        try:
            logger.info("Beginning to poll Telegram API...")
            bot.infinity_polling()
        except Exception as e:
            logger.error(f"Polling error: {e}. Restarting in 10 seconds...")
            time.sleep(10)

if __name__ == '__main__':
    # Check if required environment variables are set
    if not BOT_TOKEN or not CHANNEL_ID:
        logger.error("Missing BOT_TOKEN or CHANNEL_ID environment variables")
        logger.error("Please set these in your Render environment variables")
    else:
        start_bot()
