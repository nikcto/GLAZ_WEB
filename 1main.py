import telebot
import logging
from supabase import create_client, Client
from dotenv import load_dotenv
import os
from datetime import datetime
from statistics import handle_statistics, handle_statistics_gui, handle_stats_pagination
from tracking import handle_message, handle_text_edit, handle_delete

# Настройка логирования
def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

# Инициализация
load_dotenv('ton.env')
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Регистрация обработчиков
@bot.message_handler(commands=['statistic'])
def stats_command(message):
    handle_statistics(bot, supabase, message)

@bot.message_handler(commands=['statistic_gui'])
def stats_gui_command(message):
    handle_statistics_gui(bot, supabase, message)

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_') or call.data in ['none', 'current_page'])
def stats_pagination_handler(call):
    handle_stats_pagination(bot, supabase, call)

@bot.business_message_handler(content_types=['text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'])
def message_handler(message):
    handle_message(bot, supabase, message)

@bot.edited_business_message_handler(content_types=['text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'])
def edit_handler(message):
    handle_text_edit(bot, supabase, message)

@bot.deleted_business_messages_handler()
def delete_handler(deleted):
    handle_delete(bot, supabase, deleted)

# ... остальные обработчики команд ...

if __name__ == "__main__":
    try:
        setup_logging()
        logger.info("Bot started")
        bot.infinity_polling()
    except Exception as e:
        logger.error(f"Bot crashed: {str(e)}", exc_info=True)