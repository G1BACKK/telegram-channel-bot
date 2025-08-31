import os
import logging
from datetime import datetime, timedelta
import telebot
from telebot.types import ChatMemberUpdated
import pytz

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Configuration - will be set as environment variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_ID = os.environ.get('CHANNEL_ID')

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

# Store member join times
member_join_times = {}

def get_utc_time():
    """Get current UTC time consistently"""
    return datetime.now(pytz.utc)

@bot.message_handler(commands=['start'])
def start(message):
    """Welcome message"""
    bot.reply_to(message,
        "👋 Hi! I'm your channel member management bot.\n\n"
        "I track when members join and can remove them based on join time.\n\n"
        "📝 Usage:\n"
        "/remove_by_time YYYY-MM-DD HH:MM:SS\n\n"
        "Example:\n"
        "/remove_by_time 2023-08-01 12:00:00"
    )

@bot.message_handler(commands=['remove_by_time'])
def remove_by_time(message):
    """Remove members who joined during a specific time"""
    try:
        if message.chat.type != 'private':
            bot.reply_to(message, "Please use this command in a private chat with me.")
            return
            
        args = message.text.split()[1:]
        if len(args) < 1:
            bot.reply_to(message,
                "❌ Usage: /remove_by_time YYYY-MM-DD HH:MM:SS\n\n"
                "Example:\n"
                "/remove_by_time 2023-08-01 12:00:00\n\n"
                "This will remove users who joined within 1 minute of that time."
            )
            return
            
        # Parse the time input
        time_str = ' '.join(args[0:2]) if len(args) >= 2 else args[0] + " 00:00:00"
        target_time = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.utc)
        
        # 1-minute window around target time
        start_time = target_time - timedelta(minutes=1)
        end_time = target_time + timedelta(minutes=1)
        
        # Find matching users
        members_to_remove = []
        for user_id, join_time in member_join_times.items():
            if isinstance(join_time, datetime) and start_time <= join_time <= end_time:
                members_to_remove.append(user_id)
        
        # Remove users
        removed_count = 0
        removal_report = "🗑️ Removal Report:\n\n"
        
        for user_id in members_to_remove:
            try:
                username = member_join_times.get(f"{user_id}_username", "Unknown")
                
                bot.ban_chat_member(
                    chat_id=CHANNEL_ID, 
                    user_id=user_id,
                    until_date=datetime.now() + timedelta(seconds=30)
                )
                
                removed_count += 1
                removal_report += f"✅ Removed @{username} (joined at {member_join_times[user_id]})\n"
                
                # Clean up
                del member_join_times[user_id]
                if f"{user_id}_username" in member_join_times:
                    del member_join_times[f"{user_id}_username"]
                    
            except Exception as e:
                logger.error(f"Failed to remove user {user_id}: {e}")
                removal_report += f"❌ Failed to remove user {user_id}: {e}\n"
        
        removal_report += f"\nTotal removed: {removed_count}"
        bot.reply_to(message, removal_report)
        
    except ValueError:
        bot.reply_to(message, "❌ Invalid time format. Please use: YYYY-MM-DD HH:MM:SS")
    except Exception as e:
        logger.error(f"Error in remove_by_time: {e}")
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['list_members'])
def list_members(message):
    """List tracked members (for debugging)"""
    if not member_join_times:
        bot.reply_to(message, "No members tracked yet.")
        return
        
    report = "📊 Tracked Members:\n\n"
    for user_id, join_time in member_join_times.items():
        if not str(user_id).endswith('_username') and isinstance(join_time, datetime):
            username = member_join_times.get(f"{user_id}_username", "Unknown")
            report += f"👤 @{username} - Joined: {join_time}\n"
    
    bot.reply_to(message, report[:4000])  # Telegram message limit

@bot.chat_member_handler()
def track_chat_members(chat_member_updated):
    """Track when members join the channel"""
    try:
        if str(chat_member_updated.chat.id) != str(CHANNEL_ID):
            return
            
        user = chat_member_updated.new_chat_member.user
        old_status = chat_member_updated.old_chat_member.status
        new_status = chat_member_updated.new_chat_member.status
        
        # Check if this is a new member joining
        if old_status in ['left', 'kicked'] and new_status in ['member', 'administrator', 'creator']:
            join_time = get_utc_time()
            member_join_times[user.id] = join_time
            
            # Store username for debugging
            if user.username:
                member_join_times[f"{user.id}_username"] = user.username
                
            logger.info(f"User @{user.username} ({user.id}) joined at {join_time}")
            
    except Exception as e:
        logger.error(f"Error in track_chat_members: {e}")

if __name__ == '__main__':
    if not BOT_TOKEN or not CHANNEL_ID:
        logger.error("Missing BOT_TOKEN or CHANNEL_ID environment variables")
    else:
        logger.info("Bot started successfully!")
        bot.infinity_polling()
