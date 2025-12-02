import telebot
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import io
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from html import escape

logger = logging.getLogger(__name__)

def create_stats_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    buttons = []
    buttons.append(
        InlineKeyboardButton('⬅️', callback_data=f'stats_{current_page - 1}' if current_page > 0 else 'none'))
    buttons.append(InlineKeyboardButton(f'| {current_page + 1}/{total_pages} |', callback_data='current_page'))
    buttons.append(InlineKeyboardButton('➡️',
                                    callback_data=f'stats_{current_page + 1}' if current_page < total_pages - 1 else 'none'))
    keyboard.row(*buttons)
    return keyboard

def handle_statistics(bot, supabase, message, page: int = 0):
    try:
        user_id = message.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # ... остальной код функции ...
    except Exception as e:
        logger.error(f"Error in handle_statistics: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при получении статистики")

def handle_statistics_gui(bot, supabase, message):
    try:
        user_id = message.from_user.id
        
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # ... остальной код функции ...
    except Exception as e:
        logger.error(f"Error in handle_statistics_gui: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при создании графика")

def handle_stats_pagination(bot, supabase, call):
    try:
        if call.data == 'none':
            bot.answer_callback_query(call.id, "Больше страниц нет")
            return

        # ... остальной код функции ... 
    except Exception as e:
        logger.error(f"Error in handle_stats_pagination: {str(e)}", exc_info=True)
        bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при пагинации") 