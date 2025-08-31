import os
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext, ChatMemberHandler
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

# Store member join times
member_join_times = {}

def get_utc_time():
    """Get current UTC time consistently"""
    return datetime.now(pytz.utc)

def start(update: Update, context: CallbackContext):
    """Welcome message"""
    update.message.reply_text(
        "👋 Hi! I'm your channel member management bot.\n\n"
        "I track when members join and can remove them based on join time.\n\n"
        "📝 Usage:\n"
        "/remove_by_time YYYY-MM-DD HH:MM:SS\n\n"
        "Example:\n"
        "/remove_by_time 2023-08-01 12:00:00"
    )

def track_chat_members(update: Update, context: CallbackContext):
    """Track when members join the channel"""
    try:
        if str(update.chat_member.chat.id) != str(CHANNEL_ID):
            return
            
        user = update.chat_member.new_chat_member.user
        old_status = update.chat_member.old_chat_member.status
        new_status = update.chat_member.new_chat_member.status
        
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

def remove_by_time(update: Update, context: CallbackContext):
    """Remove members who joined during a specific time"""
    try:
        if update.message.chat.type != 'private':
            update.message.reply_text("Please use this command in a private chat with me.")
            return
            
        if len(context.args) < 1:
            update.message.reply_text(
                "❌ Usage: /remove_by_time YYYY-MM-DD HH:MM:SS\n\n"
                "Example:\n"
                "/remove_by_time 2023-08-01 12:00:00\n\n"
                "This will remove users who joined within 1 minute of that time."
            )
            return
            
        # Parse the time input
        time_str = ' '.join(context.args[0:2]) if len(context.args) >= 2 else context.args[0] + " 00:00:00"
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
                
                context.bot.ban_chat_member(
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
        update.message.reply_text(removal_report)
        
    except ValueError:
        update.message.reply_text("❌ Invalid time format. Please use: YYYY-MM-DD HH:MM:SS")
    except Exception as e:
        logger.error(f"Error in remove_by_time: {e}")
        update.message.reply_text(f"❌ Error: {e}")

def list_members(update: Update, context: CallbackContext):
    """List tracked members (for debugging)"""
    if not member_join_times:
        update.message.reply_text("No members tracked yet.")
        return
        
    report = "📊 Tracked Members:\n\n"
    for user_id, join_time in member_join_times.items():
        if not str(user_id).endswith('_username') and isinstance(join_time, datetime):
            username = member_join_times.get(f"{user_id}_username", "Unknown")
            report += f"👤 @{username} - Joined: {join_time}\n"
    
    update.message.reply_text(report[:4000])  # Telegram message limit

def main():
    """Start the bot"""
    if not BOT_TOKEN or not CHANNEL_ID:
        logger.error("Missing BOT_TOKEN or CHANNEL_ID environment variables")
        return
        
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # Add handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("remove_by_time", remove_by_time))
    dispatcher.add_handler(CommandHandler("list_members", list_members))
    dispatcher.add_handler(ChatMemberHandler(track_chat_members))

    # Start the bot
    updater.start_polling()
    logger.info("Bot started successfully!")
    updater.idle()

if __name__ == '__main__':
    main()
