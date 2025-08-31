import os
import telebot

# Configuration
BOT_TOKEN = os.environ.get('BOT_TOKEN')

if not BOT_TOKEN:
    print("Error: BOT_TOKEN environment variable is not set")
    exit(1)

# Initialize bot
bot = telebot.TeleBot(BOT_TOKEN)

try:
    # Remove any existing webhook
    bot.remove_webhook()
    print("✅ Webhook removed successfully")
    
    # Get updates to clear the queue
    updates = bot.get_updates()
    print(f"✅ Cleared {len(updates)} pending updates")
    
    print("✅ Bot has been reset. You can now start the main bot.")
    
except Exception as e:
    print(f"❌ Error during reset: {e}")
