                 "⚙️ <b>Настройка:</b>\n"
                "1. Добавьте этого бота в настройках Business аккаунта\n"
                "2. Готово! Бот начнёт отслеживать сообщения\n\n"
                
                "🔒 <b>Безопасность:</b>\n"
                "Бот хранит только метаданные сообщений и не имеет доступа к личной переписке вне бизнес-чатов.\n\n"
                
                "<code>Название чатов с названием 'неактивированный чат'/'unknown' начнут отображатся после того как вы напишите в них любое сообщение</code>"
            )
            if current_text != help_text:
                bot.edit_message_text(
                    help_text,
                    call.message.chat.id,
                    call.message.message_id,
                    parse_mode="HTML",
                    reply_markup=InlineKeyboardMarkup().row(
                        InlineKeyboardButton('🔙 Назад', callback_data='menu_main')
                    )
                )
            
        elif action == 'stats_list':
            handle_statistics(call.message)
            
        elif action == 'stats_graphs':
            handle_statistics_gui(call.message)
            
        elif action == 'onmy':
            toggle_notifications(call.message, command='onmy')
            bot.answer_callback_query(call.id, "✅ Уведомления включены")
            
        elif action == 'offmy':
            toggle_notifications(call.message, command='offmy')
            bot.answer_callback_query(call.id, "✅ Уведомления отключены")
            
        bot.answer_callback_query(call.id)
        
    except Exception as e:
        logger.error(f"Error handling menu callback: {str(e)}", exc_info=True)
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from html import escape
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import matplotlib.pyplot as plt
import io
import matplotlib as mpl

# В начале файла добавим настройку русской локализации
mpl.rcParams['font.family'] = 'DejaVu Sans'

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Отключаем логи HTTP-запросов
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Только вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация конфигурации
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Глобальные переменные
business_connection_owners = {}
messages_log = defaultdict(dict)
active_users = set()

# Добавляем словарь для отслеживания состояния админа
admin_states = {}

@bot.message_handler(commands=['statistic_gui'])
def handle_statistics_gui(message):
    try:
        user_id = message.from_user.id
        
        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        if not stats_data.data:
            bot.send_message(message.chat.id, "📊 У вас пока нет статистики сообщений")
            return

        # Создаем список чатов с их статистикой
        chat_stats = []
        
        for stat in stats_data.data:
            try:
                chat_title = get_cached_chat_title(stat['chat_id'])
            except Exception:
                chat_title = f"Неизвестный чат [{stat['chat_id']}]"

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)
        
        # Берем топ-10 чатов
        top_10_chats = chat_stats[:10]

        # Создаем график со светлым фоном
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Данные для графика
        chat_names = [chat['title'][:20] + '...' if len(chat['title']) > 20 else chat['title'] 
                     for chat in top_10_chats]
        incoming = [chat['incoming'] for chat in top_10_chats]
        outgoing = [chat['outgoing'] for chat in top_10_chats]

        # Создаем столбчатую диаграмму
        x = range(len(chat_names))
        width = 0.35

        # Добавляем значения без процентов
        def add_values(values):
            return [str(v) for v in values]

        incoming_labels = add_values(incoming)
        outgoing_labels = add_values(outgoing)

        # Рисуем столбцы с улучшенным стилем
        bars1 = ax.bar(x, incoming, width, label='Входящие', color='#2ecc71', alpha=0.8)
        bars2 = ax.bar([i + width for i in x], outgoing, width, label='Исходящие', color='#3498db', alpha=0.8)

        # Добавляем значения над столбцами
        ax.bar_label(bars1, labels=incoming_labels, padding=3, color='black')
        ax.bar_label(bars2, labels=outgoing_labels, padding=3, color='black')

        # Настройка графика
        ax.set_xlabel('Чаты', fontsize=10, color='black', labelpad=10)
        ax.set_ylabel('Количество сообщений', fontsize=10, color='black', labelpad=10)
        ax.set_title('Распределение сообщений по чатам (Топ-10)', fontsize=12, color='black', pad=20)
        
        # Настраиваем подписи осей
        plt.xticks([i + width/2 for i in x], chat_names, rotation=45, ha='right', color='black')
        plt.yticks(color='black')
        
        # Добавляем легенду
        plt.legend(loc='upper right', facecolor='white', edgecolor='black', labelcolor='black')
        
        # Устанавливаем цвет фона
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # Настраиваем отступы
        plt.tight_layout()

        # Сохраняем график в байтовый поток
        img_stream = io.BytesIO()
        plt.savefig(img_stream, format='png', dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        img_stream.seek(0)
        plt.close()

        # Отправляем изображение
        bot.send_photo(
            message.chat.id,
            photo=img_stream,
            caption="📊 <b>Топ-10 чатов по количеству сообщений</b>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating statistics GUI: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, "⚠️ Ошибка при создании визуализации статистики")


def update_user_data(user_id: int, username: str, is_connected: bool = False):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data = {
            "user_id": user_id,
            "username": username,
            "is_connected": is_connected,
            "connection_date": now if is_connected else None,
            "first_seen": now,
            "notify_self": True
        }

        result = supabase.table("users").upsert(user_data, on_conflict="user_id").execute()
        logger.info(f"User updated: {user_id} ({username}) - Connected: {is_connected}")
        return True
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}", exc_info=True)
        return False


def get_notify_setting(user_id: int) -> bool:
    try:
        result = supabase.table("users").select("notify_self").eq("user_id", user_id).execute()
        return result.data[0]["notify_self"] if result.data else True
    except Exception as e:
        logger.error(f"Error getting notify setting for {user_id}: {str(e)}", exc_info=True)
        return True


def get_connection_owner(bot, connection_id: str) -> int:
    try:
        if connection_id in business_connection_owners:
            return business_connection_owners[connection_id]

        result = supabase.table("business_connections").select("owner_id").eq("connection_id", connection_id).execute()
        if result.data:
            owner_id = result.data[0]["owner_id"]
            business_connection_owners[connection_id] = owner_id
            logger.debug(f"Cached business connection: {connection_id} -> {owner_id}")
            return owner_id

        connection = bot.get_business_connection(connection_id)
        owner_id = connection.user.id

        supabase.table("business_connections").insert({
            "connection_id": connection_id,
            "owner_id": owner_id,
            "created_at": datetime.now().isoformat()
        }).execute()

        business_connection_owners[connection_id] = owner_id
        logger.info(f"New business connection: {connection_id} -> {owner_id}")
        return owner_id

    except Exception as e:
        logger.error(f"Error getting connection owner: {str(e)}", exc_info=True)
        return None


def get_chat_title(chat: telebot.types.Chat) -> str:
    """Возвращает безопасное название чата с HTML-экранированием"""
    try:
        if chat.type == "private":
            return escape(chat.first_name or "Приватный чат")
        return escape(chat.title) if chat.title else "Без названия"
    except Exception as e:
        logger.error(f"Error getting chat title: {str(e)}")
        return "Неизвестный чат"


def get_sender_type(message, owner_id: int) -> str:
    if hasattr(message, 'from_user') and message.from_user:
        return "🟢 Ваше сообщение" if message.from_user.id == owner_id else "🔴 Сообщение собеседника"
    return "🔴 Сообщение собеседника"


def get_file_info(message):
    content_type = message.content_type
    file_id = None
    caption = getattr(message, 'caption', None)

    if content_type == 'photo':
        file_id = message.photo[-1].file_id
    elif content_type == 'video':
        file_id = message.video.file_id
    elif content_type == 'document':
        file_id = message.document.file_id
    elif content_type == 'animation':
        file_id = message.animation.file_id
    elif content_type == 'voice':
        file_id = message.voice.file_id
    elif content_type == 'sticker':
        file_id = message.sticker.file_id
    elif content_type == 'audio':
        file_id = message.audio.file_id
    elif content_type == 'location':
        file_id = f"{message.location.latitude},{message.location.longitude}"
    elif content_type == 'contact':
        file_id = f"{message.contact.phone_number}"

    return content_type, file_id, caption

chat_title_cache = {}

def get_cached_chat_title(chat_id: int) -> str:
    if chat_id not in chat_title_cache:
        try:
            chat = bot.get_chat(chat_id)
            chat_title_cache[chat_id] = get_chat_title(chat)
        except Exception as e:
            logger.error(f"Can't get chat title: {str(e)}")
            return "Unknown"
    return chat_title_cache[chat_id]

@bot.business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_message(message):
    try:
        logger.debug(f"Raw message data: {message.json}")
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            logger.warning(f"No owner for business connection: {bc_id}")
            return

        # Определяем тип сообщения
        is_outgoing = get_sender_type(message, owner_id) == "🟢 Ваше сообщение"

        # Обновляем статистику
        update_message_statistics(
            owner_id=owner_id,
            chat_id=message.chat.id,
            is_outgoing=is_outgoing
        )

        # Остальной код обработки сообщения...
        content_type, file_id, caption = get_file_info(message)
        content = message.text if content_type == 'text' else file_id

        messages_log[message.chat.id][message.message_id] = {
            'type': content_type,
            'content': content,
            'timestamp': datetime.now().timestamp(),
            'caption': caption,
            'sender_type': get_sender_type(message, owner_id),
            'chat_title': get_chat_title(message.chat)
        }

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)


def update_message_statistics(owner_id: int, chat_id: int, is_outgoing: bool):
    try:
        # Получаем текущую статистику
        stats = supabase.table("message_statistics") \
            .select("*") \
            .eq("user_id", owner_id) \
            .eq("chat_id", chat_id) \
            .execute()

        update_data = {
            "total_messages": 1,
            "outgoing" if is_outgoing else "incoming": 1
        }

        if stats.data:
            existing = stats.data[0]
            update_data = {
                "total_messages": existing['total_messages'] + 1,
                "outgoing": existing['outgoing'] + (1 if is_outgoing else 0),
                "incoming": existing['incoming'] + (0 if is_outgoing else 1)
            }

        # Upsert статистики
        supabase.table("message_statistics").upsert({
            "user_id": owner_id,
            "chat_id": chat_id,
            **update_data
        }, on_conflict="user_id,chat_id").execute()

    except Exception as e:
        logger.error(f"Error updating statistics: {str(e)}")


def create_stats_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    buttons = []

    # Добавляем кнопку "назад"
    buttons.append(InlineKeyboardButton('⬅️', callback_data=f'stats_{current_page-1}' if current_page > 0 else 'none'))
    
    # Добавляем счетчик страниц
    buttons.append(InlineKeyboardButton(f'| {current_page + 1}/{total_pages} |', callback_data='current_page'))
    
    # Добавляем кнопку "вперед"
    buttons.append(InlineKeyboardButton('➡️', callback_data=f'stats_{current_page+1}' if current_page < total_pages - 1 else 'none'))
    
    keyboard.row(*buttons)
    return keyboard

@bot.message_handler(commands=['statistic'])
def handle_statistics(message, page: int = 0):
    try:
        user_id = message.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Неактивированный чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        nopeact = 'неактивированный чат'
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
                f"\n\n<i>Про чаты с названием {nopeact} читать в /help</i>"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Отправляем сообщение с клавиатурой
        bot.send_message(
            message.chat.id,
            '\n'.join(response),
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error generating statistics: {str(e)}")
        bot.send_message(message.chat.id, "⚠️ Ошибка получения статистики")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_') or call.data in ['none', 'current_page'])
def handle_stats_pagination(call):
    try:
        if call.data == 'none':
            bot.answer_callback_query(call.id, "Больше страниц нет")
            return
        
        if call.data == 'current_page':
            bot.answer_callback_query(call.id, "нахуй ты сюда жмешь?")
            return
            
        page = int(call.data.split('_')[1])
        user_id = call.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Удалённый чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Редактируем существующее сообщение
        bot.edit_message_text(
            '\n'.join(response),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error handling stats pagination: {str(e)}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при переключении страницы")


@bot.edited_business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_text_edit(message):
    owner_id = None
    try:
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        old_data = messages_log[message.chat.id].get(message.message_id, {})
        new_content_type, new_file_id, new_caption = get_file_info(message)

        # Формируем текст уведомления
        notification = (
            f"♻️ <b>Изменено сообщение в чате:</b> {old_data.get('chat_title', 'Unknown')}\n"
            f"{old_data.get('sender_type', 'Unknown')}\n"
            f"📂 <b>Тип:</b> {old_data.get('type', 'unknown')}\n"
        )

        # Добавляем старый текст, если это текстовое сообщение
        if old_data.get('type') == 'text':
            notification += f"<b>Было:</b> {escape(old_data.get('content', ''))}\n"
            notification += f"<b>Стало:</b> {escape(message.text)}\n"

        # Если есть старая версия медиа
        if old_data.get('content') and validate_file_id(old_data['content']):
            try:
                media_method = {
                    'photo': bot.send_photo,
                    'video': bot.send_video,
                    'document': bot.send_document,
                    'animation': bot.send_animation,
                    'voice': bot.send_voice,
                    'audio': bot.send_audio,
                    'sticker': bot.send_sticker
                }.get(old_data['type'], bot.send_message)

                # Добавляем старую подпись если есть
                if old_data.get('caption'):
                    notification += f"📌 <b>Исходная подпись:</b> {escape(old_data['caption'])}"

                # Добавляем информацию о новых изменениях
                if new_caption:
                    notification += f"\n✏️ <b>Новая подпись:</b> {escape(new_caption)}"
                elif message.text:
                    notification += f"\n✏️ <b>Новый текст:</b> {escape(message.text)}"

                # Отправляем старое медиа с объединенным уведомлением
                media_method(
                    owner_id,
                    old_data['content'],
                    caption=notification,
                    parse_mode="HTML"
                )

            except Exception as e:
                logger.error(f"Ошибка отправки старого медиа: {str(e)}")
                bot.send_message(owner_id, notification + "\n🚫 <i>Не удалось прикрепить файл</i>")
        else:
            # Если нет старого медиа - отправляем только текст
            bot.send_message(owner_id, notification)

        # Обновляем кеш новой версией
        messages_log[message.chat.id][message.message_id] = {
            'type': new_content_type,
            'content': new_file_id,
            'caption': new_caption,
            'sender_type': old_data.get('sender_type'),
            'chat_title': old_data.get('chat_title'),
            'timestamp': datetime.now().timestamp()
        }

    except Exception as exc:
        logger.error(f"Error handling edit: {str(exc)}", exc_info=True)
        if owner_id:
            error_msg = f"⚠️ Ошибка обработки изменения: {escape(str(exc))}" if exc else "Неизвестная ошибка"
            bot.send_message(owner_id, error_msg)


@bot.deleted_business_messages_handler()
def handle_delete(deleted):
    try:
        bc_id = deleted.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        notify_self = get_notify_setting(owner_id)

        for msg_id in deleted.message_ids:
            data = messages_log[deleted.chat.id].pop(msg_id, None)
            if not data:
                continue

            if data.get('sender_type') == "🟢 Ваше сообщение" and not notify_self:
                continue

            notification = (
                f"🗑️ <b>Удалено сообщение в чате:</b> {data.get('chat_title', 'Неизвестный чат')}\n"
                f"{data.get('sender_type', '❓ Неизвестный отправитель')}\n"
                f"📂 <b>Тип:</b> {data['type']}\n"
            )

            try:
                # Для медиа-файлов используем актуальный file_id из кеша
                if data['type'] in ['photo', 'video', 'document', 'animation']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'photo': bot.send_photo,
                        'video': bot.send_video,
                        'document': bot.send_document,
                        'animation': bot.send_animation
                    }[data['type']]

                    if data.get('caption'):
                        notification += f"📌 <b>Подпись:</b> {escape(data['caption'])}\n"

                    send_media(owner_id, file_id, caption=notification)
                    logger.debug(f"Sent media with ID: {file_id}")

                elif data['type'] == 'text':
                    notification += f"📝 <b>Содержимое:</b>\n{escape(data['content'])}"
                    bot.send_message(owner_id, notification)

                elif data['type'] in ['voice', 'audio', 'sticker']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'voice': bot.send_voice,
                        'audio': bot.send_audio,
                        'sticker': bot.send_sticker
                    }[data['type']]
                    send_media(owner_id, file_id)
                    bot.send_message(owner_id, notification)

            except Exception as e:
                logger.error(f"Error processing deleted media {msg_id}: {str(e)}")
                bot.send_message(owner_id, f"⚠️ Не удалось восстановить {data['type']}: {escape(str(e))}")
                # Отправляем текстовую информацию о файле
                bot.send_message(owner_id, notification + f"\n🚫 Идентификатор файла: {file_id}")

    except Exception as e:
        logger.error(f"Error processing delete event: {str(e)}", exc_info=True)


def validate_file_id(file_id: str) -> bool:
    """Улучшенная валидация file_id"""
    try:
        if not isinstance(file_id, str):
            return False
        if len(file_id) < 20 or len(file_id) > 255:
            return False
        return all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in file_id)
    except:
        return False


@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user = message.from_user
        username = user.username or user.first_name or f"User_{user.id}"
        logger.info(f"Command /start from {user.id} ({username})")

        result = supabase.table("users").select("user_id").eq("user_id", user.id).execute()

        if not result.data:
            logger.info(f"New user registered: {user.id} ({username})")
            if update_user_data(user.id, username):
                active_users.add(user.id)
            else:
                logger.error(f"Failed to register user: {user.id}")

        bot.send_message(message.chat.id, "Инструкция в описании \n<b>Наблюдаю!👀</b>\nДля управления используйте /menu")

    except Exception as e:
        logger.error(f"Error in start_command: {str(e)}", exc_info=True)


@bot.message_handler(commands=['onmy', 'offmy'])
def toggle_notifications(message):
    try:
        user = message.from_user
        # Получаем команду из текста сообщения
        command = message.text.split()[0].lower().replace('/', '')
        new_value = command == 'onmy'

        supabase.table("users").update({"notify_self": new_value}).eq("user_id", user.id).execute()
        status = "включены" if new_value else "отключены"
        logger.info(f"Notifications toggled: {user.id} -> {status}")
        bot.reply_to(message, f"🔔 Уведомления о ваших сообщениях теперь {status}")

    except Exception as e:
        logger.error(f"Error toggling notifications: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при изменении настроек")


@bot.business_connection_handler(func=lambda connection: True)
def handle_business_connection(business_connection):
    try:
        user = business_connection.user
        username = user.username or user.first_name or f"User_{user.id}"

        if business_connection.date > 0:
            logger.info(f"Business connection established: {user.id} ({username})")
            update_user_data(user.id, username, True)
            business_connection_owners[business_connection.id] = user.id
        else:
            logger.info(f"Business connection removed: {user.id} ({username})")
            update_user_data(user.id, username, False)
            if business_connection.id in business_connection_owners:
                del business_connection_owners[business_connection.id]

    except Exception as e:
        logger.error(f"Error handling business connection: {str(e)}", exc_info=True)


def split_message(text: str, max_length: int = 4096) -> list:
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]


@bot.message_handler(commands=['stat'])
def handle_stats(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized stats access attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        logger.info(f"Generating stats for admin {ADMIN_ID}")
        users_data = supabase.table("users").select("*").order("first_seen", desc=True).execute()
        report = ["📊 <b>Статистика</b>\nВсего пользователей: {}".format(len(users_data.data))]

        for user in users_data.data:
            status = "✅ Подключен" if user["is_connected"] else "❌ Отключен"
            report.append(
                f"\n👤 {escape(user['username'])} (ID: {user['user_id']})\n"
                f"Статус: {status}\n"
                f"Первое использование: {user['first_seen']}\n"
                f"Последнее подключение: {user['connection_date'] or 'Нет'}"
            )

        for part in split_message('\n'.join(report)):
            bot.send_message(message.chat.id, part, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating stats: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {escape(str(e))}")


@bot.message_handler(commands=['tell'])
def handle_tell_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized tell attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        admin_states['waiting_for_broadcast'] = True
        bot.reply_to(message, "📢 Отправьте сообщение для рассылки всем пользователям\n"
                            "Поддерживаются текст и фото с подписью\n"
                            "Для отмены используйте команду /stop")
        
    except Exception as e:
        logger.error(f"Error in tell command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка")

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return

        if admin_states.get('waiting_for_broadcast'):
            admin_states['waiting_for_broadcast'] = False
            bot.reply_to(message, "✅ Команда рассылки отменена")
            logger.info(f"Broadcast cancelled by admin")
        
    except Exception as e:
        logger.error(f"Error in stop command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отмене команды")

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and admin_states.get('waiting_for_broadcast'),
                    content_types=['text', 'photo'])
def handle_broadcast_message(message):
    try:
        admin_states['waiting_for_broadcast'] = False
        
        # Получаем всех пользователей из базы
        users = supabase.table("users").select("user_id").execute()
        
        success_count = 0
        fail_count = 0
        
        for user in users.data:
            try:
                if message.content_type == 'photo':
                    # Для фото берём последнее (самое большое) изображение
                    photo = message.photo[-1].file_id
                    bot.send_photo(user['user_id'], photo, caption=message.caption)
                else:
                    bot.send_message(user['user_id'], message.text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user['user_id']}: {str(e)}")
                fail_count += 1
                
        report = (f"📊 Рассылка завершена\n"
                 f"✅ Успешно отправлено: {success_count}\n"
                 f"❌ Ошибок отправки: {fail_count}")
        
        bot.reply_to(message, report)
        logger.info(f"Broadcast completed: {success_count} successful, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при рассылке")


@bot.message_handler(commands=['help'])
def help_command(message):
    try:
        help_text = (
            "🤖 <b>О боте:</b>\n"
            "Этот бот помогает отслеживать сообщения в ваших бизнес-чатах Telegram. "
            "Он уведомляет вас об удалённых и отредактированных сообщениях.\n\n"
            
            "📝 <b>Основные команды:</b>\n"
            "• /start - Запустить бота\n"
            "• /statistic - Показать статистику сообщений\n"
            "• /onmy - Включить уведомления о ваших удалённых сообщениях\n"
            "• /offmy - Отключить уведомления о ваших удалённых сообщениях\n\n"
            
            "⚙️ <b>Настройка:</b>\n"
            "1. Добавьте этого бота в настройках Business аккаунта\n"
            "2. Готово! Бот начнёт отслеживать сообщения\n\n"

            
            "🔒 <b>Безопасность:</b>\n"
            "Бот хранит только метаданные сообщений и не имеет доступа к личной переписке вне бизнес-чатов."

            "\n\n<code>Название чатов с названием 'неактивированный чат'/'unknown' начнут отображатся после того как вы напишите в них любое сообщение</code>"
        )
        
        bot.send_message(message.chat.id, help_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отображении справки")


if __name__ == "__main__":
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot crashed: {str(e)}")import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from html import escape
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import matplotlib.pyplot as plt
import io
import matplotlib as mpl

# В начале файла добавим настройку русской локализации
mpl.rcParams['font.family'] = 'DejaVu Sans'

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Отключаем логи HTTP-запросов
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Только вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация конфигурации
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Глобальные переменные
business_connection_owners = {}
messages_log = defaultdict(dict)
active_users = set()

# Добавляем словарь для отслеживания состояния админа
admin_states = {}

@bot.message_handler(commands=['statistic_gui'])
def handle_statistics_gui(message):
    try:
        user_id = message.from_user.id
        
        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        if not stats_data.data:
            bot.send_message(message.chat.id, "📊 У вас пока нет статистики сообщений")
            return

        # Создаем список чатов с их статистикой
        chat_stats = []
        
        for stat in stats_data.data:
            try:
                chat_title = get_cached_chat_title(stat['chat_id'])
            except Exception:
                chat_title = f"Неизвестный чат [{stat['chat_id']}]"

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)
        
        # Берем топ-10 чатов
        top_10_chats = chat_stats[:10]

        # Создаем график со светлым фоном
        plt.style.use('default')
        fig, ax = plt.subplots(figsize=(12, 6))
        
        # Данные для графика
        chat_names = [chat['title'][:20] + '...' if len(chat['title']) > 20 else chat['title'] 
                     for chat in top_10_chats]
        incoming = [chat['incoming'] for chat in top_10_chats]
        outgoing = [chat['outgoing'] for chat in top_10_chats]

        # Создаем столбчатую диаграмму
        x = range(len(chat_names))
        width = 0.35

        # Добавляем значения без процентов
        def add_values(values):
            return [str(v) for v in values]

        incoming_labels = add_values(incoming)
        outgoing_labels = add_values(outgoing)

        # Рисуем столбцы с улучшенным стилем
        bars1 = ax.bar(x, incoming, width, label='Входящие', color='#2ecc71', alpha=0.8)
        bars2 = ax.bar([i + width for i in x], outgoing, width, label='Исходящие', color='#3498db', alpha=0.8)

        # Добавляем значения над столбцами
        ax.bar_label(bars1, labels=incoming_labels, padding=3, color='black')
        ax.bar_label(bars2, labels=outgoing_labels, padding=3, color='black')

        # Настройка графика
        ax.set_xlabel('Чаты', fontsize=10, color='black', labelpad=10)
        ax.set_ylabel('Количество сообщений', fontsize=10, color='black', labelpad=10)
        ax.set_title('Распределение сообщений по чатам (Топ-10)', fontsize=12, color='black', pad=20)
        
        # Настраиваем подписи осей
        plt.xticks([i + width/2 for i in x], chat_names, rotation=45, ha='right', color='black')
        plt.yticks(color='black')
        
        # Добавляем легенду
        plt.legend(loc='upper right', facecolor='white', edgecolor='black', labelcolor='black')
        
        # Устанавливаем цвет фона
        ax.set_facecolor('white')
        fig.patch.set_facecolor('white')
        
        # Настраиваем отступы
        plt.tight_layout()

        # Сохраняем график в байтовый поток
        img_stream = io.BytesIO()
        plt.savefig(img_stream, format='png', dpi=300, bbox_inches='tight', 
                   facecolor='white', edgecolor='none')
        img_stream.seek(0)
        plt.close()

        # Отправляем изображение
        bot.send_photo(
            message.chat.id,
            photo=img_stream,
            caption=f"📊 <b>Топ-10 чатов по количеству сообщений</b>\n\n<i>Про чаты с названием Unknown читать в /help</i>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating statistics GUI: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, "⚠️ Ошибка при создании визуализации статистики")


def update_user_data(user_id: int, username: str, is_connected: bool = False):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data = {
            "user_id": user_id,
            "username": username,
            "is_connected": is_connected,
            "connection_date": now if is_connected else None,
            "first_seen": now,
            "notify_self": True
        }

        result = supabase.table("users").upsert(user_data, on_conflict="user_id").execute()
        logger.info(f"User updated: {user_id} ({username}) - Connected: {is_connected}")
        return True
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}", exc_info=True)
        return False


def get_notify_setting(user_id: int) -> bool:
    try:
        result = supabase.table("users").select("notify_self").eq("user_id", user_id).execute()
        return result.data[0]["notify_self"] if result.data else True
    except Exception as e:
        logger.error(f"Error getting notify setting for {user_id}: {str(e)}", exc_info=True)
        return True


def get_connection_owner(bot, connection_id: str) -> int:
    try:
        if connection_id in business_connection_owners:
            return business_connection_owners[connection_id]

        result = supabase.table("business_connections").select("owner_id").eq("connection_id", connection_id).execute()
        if result.data:
            owner_id = result.data[0]["owner_id"]
            business_connection_owners[connection_id] = owner_id
            logger.debug(f"Cached business connection: {connection_id} -> {owner_id}")
            return owner_id

        connection = bot.get_business_connection(connection_id)
        owner_id = connection.user.id

        supabase.table("business_connections").insert({
            "connection_id": connection_id,
            "owner_id": owner_id,
            "created_at": datetime.now().isoformat()
        }).execute()

        business_connection_owners[connection_id] = owner_id
        logger.info(f"New business connection: {connection_id} -> {owner_id}")
        return owner_id

    except Exception as e:
        logger.error(f"Error getting connection owner: {str(e)}", exc_info=True)
        return None


def get_chat_title(chat: telebot.types.Chat) -> str:
    """Возвращает безопасное название чата с HTML-экранированием"""
    try:
        if chat.type == "private":
            return escape(chat.first_name or "Приватный чат")
        return escape(chat.title) if chat.title else "Без названия"
    except Exception as e:
        logger.error(f"Error getting chat title: {str(e)}")
        return "Неизвестный чат"


def get_sender_type(message, owner_id: int) -> str:
    if hasattr(message, 'from_user') and message.from_user:
        return "🟢 Ваше сообщение" if message.from_user.id == owner_id else "🔴 Сообщение собеседника"
    return "🔴 Сообщение собеседника"


def get_file_info(message):
    content_type = message.content_type
    file_id = None
    caption = getattr(message, 'caption', None)

    if content_type == 'photo':
        file_id = message.photo[-1].file_id
    elif content_type == 'video':
        file_id = message.video.file_id
    elif content_type == 'document':
        file_id = message.document.file_id
    elif content_type == 'animation':
        file_id = message.animation.file_id
    elif content_type == 'voice':
        file_id = message.voice.file_id
    elif content_type == 'sticker':
        file_id = message.sticker.file_id
    elif content_type == 'audio':
        file_id = message.audio.file_id
    elif content_type == 'location':
        file_id = f"{message.location.latitude},{message.location.longitude}"
    elif content_type == 'contact':
        file_id = f"{message.contact.phone_number}"

    return content_type, file_id, caption

chat_title_cache = {}

def get_cached_chat_title(chat_id: int) -> str:
    if chat_id not in chat_title_cache:
        try:
            chat = bot.get_chat(chat_id)
            chat_title_cache[chat_id] = get_chat_title(chat)
        except Exception as e:
            logger.error(f"Can't get chat title: {str(e)}")
            return "Unknown"
    return chat_title_cache[chat_id]

@bot.business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_message(message):
    try:
        logger.debug(f"Raw message data: {message.json}")
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            logger.warning(f"No owner for business connection: {bc_id}")
            return

        # Определяем тип сообщения
        is_outgoing = get_sender_type(message, owner_id) == "🟢 Ваше сообщение"

        # Обновляем статистику
        update_message_statistics(
            owner_id=owner_id,
            chat_id=message.chat.id,
            is_outgoing=is_outgoing
        )

        # Остальной код обработки сообщения...
        content_type, file_id, caption = get_file_info(message)
        content = message.text if content_type == 'text' else file_id

        messages_log[message.chat.id][message.message_id] = {
            'type': content_type,
            'content': content,
            'timestamp': datetime.now().timestamp(),
            'caption': caption,
            'sender_type': get_sender_type(message, owner_id),
            'chat_title': get_chat_title(message.chat)
        }

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)


def update_message_statistics(owner_id: int, chat_id: int, is_outgoing: bool):
    try:
        # Получаем текущую статистику
        stats = supabase.table("message_statistics") \
            .select("*") \
            .eq("user_id", owner_id) \
            .eq("chat_id", chat_id) \
            .execute()

        update_data = {
            "total_messages": 1,
            "outgoing" if is_outgoing else "incoming": 1
        }

        if stats.data:
            existing = stats.data[0]
            update_data = {
                "total_messages": existing['total_messages'] + 1,
                "outgoing": existing['outgoing'] + (1 if is_outgoing else 0),
                "incoming": existing['incoming'] + (0 if is_outgoing else 1)
            }

        # Upsert статистики
        supabase.table("message_statistics").upsert({
            "user_id": owner_id,
            "chat_id": chat_id,
            **update_data
        }, on_conflict="user_id,chat_id").execute()

    except Exception as e:
        logger.error(f"Error updating statistics: {str(e)}")


def create_stats_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    buttons = []

    # Добавляем кнопку "назад"
    buttons.append(InlineKeyboardButton('⬅️', callback_data=f'stats_{current_page-1}' if current_page > 0 else 'none'))
    
    # Добавляем счетчик страниц
    buttons.append(InlineKeyboardButton(f'| {current_page + 1}/{total_pages} |', callback_data='current_page'))
    
    # Добавляем кнопку "вперед"
    buttons.append(InlineKeyboardButton('➡️', callback_data=f'stats_{current_page+1}' if current_page < total_pages - 1 else 'none'))
    
    keyboard.row(*buttons)
    return keyboard

@bot.message_handler(commands=['statistic'])
def handle_statistics(message, page: int = 0):
    try:
        user_id = message.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Неактивированный чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        nopeact = 'неактивированный чат'
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
                f"\n\n<i>Про чаты с названием {nopeact} читать в /help</i>"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Отправляем сообщение с клавиатурой
        bot.send_message(
            message.chat.id,
            '\n'.join(response),
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error generating statistics: {str(e)}")
        bot.send_message(message.chat.id, "⚠️ Ошибка получения статистики")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_') or call.data in ['none', 'current_page'])
def handle_stats_pagination(call):
    try:
        if call.data == 'none':
            bot.answer_callback_query(call.id, "Больше страниц нет")
            return
        
        if call.data == 'current_page':
            bot.answer_callback_query(call.id, "нахуй ты сюда жмешь?")
            return
            
        page = int(call.data.split('_')[1])
        user_id = call.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Удалённый чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Редактируем существующее сообщение
        bot.edit_message_text(
            '\n'.join(response),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error handling stats pagination: {str(e)}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при переключении страницы")


@bot.edited_business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_text_edit(message):
    owner_id = None
    try:
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        old_data = messages_log[message.chat.id].get(message.message_id, {})
        new_content_type, new_file_id, new_caption = get_file_info(message)

        # Формируем текст уведомления
        notification = (
            f"♻️ <b>Изменено сообщение в чате:</b> {old_data.get('chat_title', 'Unknown')}\n"
            f"{old_data.get('sender_type', 'Unknown')}\n"
            f"📂 <b>Тип:</b> {old_data.get('type', 'unknown')}\n"
        )

        # Добавляем старый текст, если это текстовое сообщение
        if old_data.get('type') == 'text':
            notification += f"<b>Было:</b> {escape(old_data.get('content', ''))}\n"
            notification += f"<b>Стало:</b> {escape(message.text)}\n"

        # Если есть старая версия медиа
        if old_data.get('content') and validate_file_id(old_data['content']):
            try:
                media_method = {
                    'photo': bot.send_photo,
                    'video': bot.send_video,
                    'document': bot.send_document,
                    'animation': bot.send_animation,
                    'voice': bot.send_voice,
                    'audio': bot.send_audio,
                    'sticker': bot.send_sticker
                }.get(old_data['type'], bot.send_message)

                # Добавляем старую подпись если есть
                if old_data.get('caption'):
                    notification += f"📌 <b>Исходная подпись:</b> {escape(old_data['caption'])}"

                # Добавляем информацию о новых изменениях
                if new_caption:
                    notification += f"\n✏️ <b>Новая подпись:</b> {escape(new_caption)}"
                elif message.text:
                    notification += f"\n✏️ <b>Новый текст:</b> {escape(message.text)}"

                # Отправляем старое медиа с объединенным уведомлением
                media_method(
                    owner_id,
                    old_data['content'],
                    caption=notification,
                    parse_mode="HTML"
                )

            except Exception as e:
                logger.error(f"Ошибка отправки старого медиа: {str(e)}")
                bot.send_message(owner_id, notification + "\n🚫 <i>Не удалось прикрепить файл</i>")
        else:
            # Если нет старого медиа - отправляем только текст
            bot.send_message(owner_id, notification)

        # Обновляем кеш новой версией
        messages_log[message.chat.id][message.message_id] = {
            'type': new_content_type,
            'content': new_file_id,
            'caption': new_caption,
            'sender_type': old_data.get('sender_type'),
            'chat_title': old_data.get('chat_title'),
            'timestamp': datetime.now().timestamp()
        }

    except Exception as exc:
        logger.error(f"Error handling edit: {str(exc)}", exc_info=True)
        if owner_id:
            error_msg = f"⚠️ Ошибка обработки изменения: {escape(str(exc))}" if exc else "Неизвестная ошибка"
            bot.send_message(owner_id, error_msg)


@bot.deleted_business_messages_handler()
def handle_delete(deleted):
    try:
        bc_id = deleted.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        notify_self = get_notify_setting(owner_id)

        for msg_id in deleted.message_ids:
            data = messages_log[deleted.chat.id].pop(msg_id, None)
            if not data:
                continue

            if data.get('sender_type') == "🟢 Ваше сообщение" and not notify_self:
                continue

            notification = (
                f"🗑️ <b>Удалено сообщение в чате:</b> {data.get('chat_title', 'Неизвестный чат')}\n"
                f"{data.get('sender_type', '❓ Неизвестный отправитель')}\n"
                f"📂 <b>Тип:</b> {data['type']}\n"
            )

            try:
                # Для медиа-файлов используем актуальный file_id из кеша
                if data['type'] in ['photo', 'video', 'document', 'animation']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'photo': bot.send_photo,
                        'video': bot.send_video,
                        'document': bot.send_document,
                        'animation': bot.send_animation
                    }[data['type']]

                    if data.get('caption'):
                        notification += f"📌 <b>Подпись:</b> {escape(data['caption'])}\n"

                    send_media(owner_id, file_id, caption=notification)
                    logger.debug(f"Sent media with ID: {file_id}")

                elif data['type'] == 'text':
                    notification += f"📝 <b>Содержимое:</b>\n{escape(data['content'])}"
                    bot.send_message(owner_id, notification)

                elif data['type'] in ['voice', 'audio', 'sticker']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'voice': bot.send_voice,
                        'audio': bot.send_audio,
                        'sticker': bot.send_sticker
                    }[data['type']]
                    send_media(owner_id, file_id)
                    bot.send_message(owner_id, notification)

            except Exception as e:
                logger.error(f"Error processing deleted media {msg_id}: {str(e)}")
                bot.send_message(owner_id, f"⚠️ Не удалось восстановить {data['type']}: {escape(str(e))}")
                # Отправляем текстовую информацию о файле
                bot.send_message(owner_id, notification + f"\n🚫 Идентификатор файла: {file_id}")

    except Exception as e:
        logger.error(f"Error processing delete event: {str(e)}", exc_info=True)


def validate_file_id(file_id: str) -> bool:
    """Улучшенная валидация file_id"""
    try:
        if not isinstance(file_id, str):
            return False
        if len(file_id) < 20 or len(file_id) > 255:
            return False
        return all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in file_id)
    except:
        return False


@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user = message.from_user
        username = user.username or user.first_name or f"User_{user.id}"
        logger.info(f"Command /start from {user.id} ({username})")

        result = supabase.table("users").select("user_id").eq("user_id", user.id).execute()

        if not result.data:
            logger.info(f"New user registered: {user.id} ({username})")
            if update_user_data(user.id, username):
                active_users.add(user.id)
            else:
                logger.error(f"Failed to register user: {user.id}")

        bot.send_message(message.chat.id, "Инструкция в описании \n<b>Наблюдаю!👀</b>")

    except Exception as e:
        logger.error(f"Error in start_command: {str(e)}", exc_info=True)


@bot.message_handler(commands=['onmy', 'offmy'])
def toggle_notifications(message):
    try:
        user = message.from_user
        # Получаем команду из текста сообщения
        command = message.text.split()[0].lower().replace('/', '')
        new_value = command == 'onmy'

        supabase.table("users").update({"notify_self": new_value}).eq("user_id", user.id).execute()
        status = "включены" if new_value else "отключены"
        logger.info(f"Notifications toggled: {user.id} -> {status}")
        bot.reply_to(message, f"🔔 Уведомления о ваших сообщениях теперь {status}")

    except Exception as e:
        logger.error(f"Error toggling notifications: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при изменении настроек")


@bot.business_connection_handler(func=lambda connection: True)
def handle_business_connection(business_connection):
    try:
        user = business_connection.user
        username = user.username or user.first_name or f"User_{user.id}"

        if business_connection.date > 0:
            logger.info(f"Business connection established: {user.id} ({username})")
            update_user_data(user.id, username, True)
            business_connection_owners[business_connection.id] = user.id
        else:
            logger.info(f"Business connection removed: {user.id} ({username})")
            update_user_data(user.id, username, False)
            if business_connection.id in business_connection_owners:
                del business_connection_owners[business_connection.id]

    except Exception as e:
        logger.error(f"Error handling business connection: {str(e)}", exc_info=True)


def split_message(text: str, max_length: int = 4096) -> list:
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]


@bot.message_handler(commands=['stat'])
def handle_stats(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized stats access attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        logger.info(f"Generating stats for admin {ADMIN_ID}")
        users_data = supabase.table("users").select("*").order("first_seen", desc=True).execute()
        report = ["📊 <b>Статистика</b>\nВсего пользователей: {}".format(len(users_data.data))]

        for user in users_data.data:
            status = "✅ Подключен" if user["is_connected"] else "❌ Отключен"
            report.append(
                f"\n👤 {escape(user['username'])} (ID: {user['user_id']})\n"
                f"Статус: {status}\n"
                f"Первое использование: {user['first_seen']}\n"
                f"Последнее подключение: {user['connection_date'] or 'Нет'}"
            )

        for part in split_message('\n'.join(report)):
            bot.send_message(message.chat.id, part, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating stats: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {escape(str(e))}")


@bot.message_handler(commands=['tell'])
def handle_tell_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized tell attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        admin_states['waiting_for_broadcast'] = True
        bot.reply_to(message, "📢 Отправьте сообщение для рассылки всем пользователям\n"
                            "Поддерживаются текст и фото с подписью\n"
                            "Для отмены используйте команду /stop")
        
    except Exception as e:
        logger.error(f"Error in tell command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка")

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return

        if admin_states.get('waiting_for_broadcast'):
            admin_states['waiting_for_broadcast'] = False
            bot.reply_to(message, "✅ Команда рассылки отменена")
            logger.info(f"Broadcast cancelled by admin")
        
    except Exception as e:
        logger.error(f"Error in stop command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отмене команды")

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and admin_states.get('waiting_for_broadcast'),
                    content_types=['text', 'photo'])
def handle_broadcast_message(message):
    try:
        admin_states['waiting_for_broadcast'] = False
        
        # Получаем всех пользователей из базы
        users = supabase.table("users").select("user_id").execute()
        
        success_count = 0
        fail_count = 0
        
        for user in users.data:
            try:
                if message.content_type == 'photo':
                    # Для фото берём последнее (самое большое) изображение
                    photo = message.photo[-1].file_id
                    bot.send_photo(user['user_id'], photo, caption=message.caption)
                else:
                    bot.send_message(user['user_id'], message.text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user['user_id']}: {str(e)}")
                fail_count += 1
                
        report = (f"📊 Рассылка завершена\n"
                 f"✅ Успешно отправлено: {success_count}\n"
                 f"❌ Ошибок отправки: {fail_count}")
        
        bot.reply_to(message, report)
        logger.info(f"Broadcast completed: {success_count} successful, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при рассылке")


@bot.message_handler(commands=['help'])
def help_command(message):
    try:
        help_text = (
            "🤖 <b>О боте:</b>\n"
            "Этот бот помогает отслеживать сообщения в ваших бизнес-чатах Telegram. "
            "Он уведомляет вас об удалённых и отредактированных сообщениях.\n\n"
            
            "📝 <b>Основные команды:</b>\n"
            "• /start - Запустить бота\n"
            "• /statistic - Показать статистику сообщений\n"
            "• /onmy - Включить уведомления о ваших удалённых сообщениях\n"
            "• /offmy - Отключить уведомления о ваших удалённых сообщениях\n\n"
            
            "⚙️ <b>Настройка:</b>\n"
            "1. Добавьте этого бота в настройках Business аккаунта\n"
            "2. Готово! Бот начнёт отслеживать сообщения\n\n"

            
            "🔒 <b>Безопасность:</b>\n"
            "Бот хранит только метаданные сообщений и не имеет доступа к личной переписке вне бизнес-чатов."

            "\n\n<code>Название чатов с названием 'неактивированный чат'/'unknown' начнут отображатся после того как вы напишите в них любое сообщение</code>"
        )
        
        bot.send_message(message.chat.id, help_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отображении справки")


if __name__ == "__main__":
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot crashed: {str(e)}")import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv
from html import escape
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import matplotlib.pyplot as plt
import io
import matplotlib as mpl

# В начале файла добавим настройку русской локализации
mpl.rcParams['font.family'] = 'DejaVu Sans'

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Отключаем логи HTTP-запросов
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Только вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация конфигурации
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Глобальные переменные
business_connection_owners = {}
messages_log = defaultdict(dict)
active_users = set()

# Добавляем словарь для отслеживания состояния админа
admin_states = {}

@bot.message_handler(commands=['statistic_gui'])
def handle_statistics_gui(message):
    try:
        user_id = message.from_user.id
        
        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        if not stats_data.data:
            bot.send_message(message.chat.id, "📊 У вас пока нет статистики сообщений")
            return

        # Создаем список чатов с их статистикой
        chat_stats = []
        
        for stat in stats_data.data:
            try:
                chat_title = get_cached_chat_title(stat['chat_id'])
            except Exception:
                chat_title = f"Неактивированный чат ({stat['chat_id']})"

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)
        
        # Берем топ-10 чатов
        top_10_chats = chat_stats[:10]

        # Создаем график
        plt.figure(figsize=(12, 6))
        
        # Данные для графика
        chat_names = [chat['title'][:20] + '...' if len(chat['title']) > 20 else chat['title'] 
                     for chat in top_10_chats]
        incoming = [chat['incoming'] for chat in top_10_chats]
        outgoing = [chat['outgoing'] for chat in top_10_chats]

        # Создаем столбчатую диаграмму
        x = range(len(chat_names))
        width = 0.35

        plt.bar(x, incoming, width, label='Входящие', color='#FF6B6B')
        plt.bar([i + width for i in x], outgoing, width, label='Исходящие', color='#4ECDC4')

        # Настройка графика
        plt.xlabel('Чаты')
        plt.ylabel('Количество сообщений')
        plt.title('Распределение сообщений по чатам (Топ-10)')
        plt.xticks([i + width/2 for i in x], chat_names, rotation=45, ha='right')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.tight_layout()

        # Сохраняем график в байтовый поток
        img_stream = io.BytesIO()
        plt.savefig(img_stream, format='png', dpi=300, bbox_inches='tight')
        img_stream.seek(0)
        plt.close()

        # Отправляем изображение
        bot.send_photo(
            message.chat.id,
            photo=img_stream,
            caption="📊 <b>Топ-10 чатов по количеству сообщений</b>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Error generating statistics GUI: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, "⚠️ Ошибка при создании визуализации статистики")


# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Отключаем логи HTTP-запросов
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Только вывод в консоль
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


setup_logging()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация конфигурации
bot = telebot.TeleBot(os.getenv("BOT_TOKEN"), parse_mode="HTML")
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
ADMIN_ID = int(os.getenv("ADMIN_ID"))

# Глобальные переменные
business_connection_owners = {}
messages_log = defaultdict(dict)
active_users = set()

# Добавляем словарь для отслеживания состояния админа
admin_states = {}


def update_user_data(user_id: int, username: str, is_connected: bool = False):
    try:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data = {
            "user_id": user_id,
            "username": username,
            "is_connected": is_connected,
            "connection_date": now if is_connected else None,
            "first_seen": now,
            "notify_self": True
        }

        result = supabase.table("users").upsert(user_data, on_conflict="user_id").execute()
        logger.info(f"User updated: {user_id} ({username}) - Connected: {is_connected}")
        return True
    except Exception as e:
        logger.error(f"Error updating user {user_id}: {str(e)}", exc_info=True)
        return False


def get_notify_setting(user_id: int) -> bool:
    try:
        result = supabase.table("users").select("notify_self").eq("user_id", user_id).execute()
        return result.data[0]["notify_self"] if result.data else True
    except Exception as e:
        logger.error(f"Error getting notify setting for {user_id}: {str(e)}", exc_info=True)
        return True


def get_connection_owner(bot, connection_id: str) -> int:
    try:
        if connection_id in business_connection_owners:
            return business_connection_owners[connection_id]

        result = supabase.table("business_connections").select("owner_id").eq("connection_id", connection_id).execute()
        if result.data:
            owner_id = result.data[0]["owner_id"]
            business_connection_owners[connection_id] = owner_id
            logger.debug(f"Cached business connection: {connection_id} -> {owner_id}")
            return owner_id

        connection = bot.get_business_connection(connection_id)
        owner_id = connection.user.id

        supabase.table("business_connections").insert({
            "connection_id": connection_id,
            "owner_id": owner_id,
            "created_at": datetime.now().isoformat()
        }).execute()

        business_connection_owners[connection_id] = owner_id
        logger.info(f"New business connection: {connection_id} -> {owner_id}")
        return owner_id

    except Exception as e:
        logger.error(f"Error getting connection owner: {str(e)}", exc_info=True)
        return None


def get_chat_title(chat: telebot.types.Chat) -> str:
    """Возвращает безопасное название чата с HTML-экранированием"""
    try:
        if chat.type == "private":
            return escape(chat.first_name or "Приватный чат")
        return escape(chat.title) if chat.title else "Без названия"
    except Exception as e:
        logger.error(f"Error getting chat title: {str(e)}")
        return "Неизвестный чат"


def get_sender_type(message, owner_id: int) -> str:
    if hasattr(message, 'from_user') and message.from_user:
        return "🟢 Ваше сообщение" if message.from_user.id == owner_id else "🔴 Сообщение собеседника"
    return "🔴 Сообщение собеседника"


def get_file_info(message):
    content_type = message.content_type
    file_id = None
    caption = getattr(message, 'caption', None)

    if content_type == 'photo':
        file_id = message.photo[-1].file_id
    elif content_type == 'video':
        file_id = message.video.file_id
    elif content_type == 'document':
        file_id = message.document.file_id
    elif content_type == 'animation':
        file_id = message.animation.file_id
    elif content_type == 'voice':
        file_id = message.voice.file_id
    elif content_type == 'sticker':
        file_id = message.sticker.file_id
    elif content_type == 'audio':
        file_id = message.audio.file_id
    elif content_type == 'location':
        file_id = f"{message.location.latitude},{message.location.longitude}"
    elif content_type == 'contact':
        file_id = f"{message.contact.phone_number}"

    return content_type, file_id, caption

chat_title_cache = {}

def get_cached_chat_title(chat_id: int) -> str:
    if chat_id not in chat_title_cache:
        try:
            chat = bot.get_chat(chat_id)
            chat_title_cache[chat_id] = get_chat_title(chat)
        except Exception as e:
            logger.error(f"Can't get chat title: {str(e)}")
            return "Unknown"
    return chat_title_cache[chat_id]

@bot.business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_message(message):
    try:
        logger.debug(f"Raw message data: {message.json}")
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            logger.warning(f"No owner for business connection: {bc_id}")
            return

        # Определяем тип сообщения
        is_outgoing = get_sender_type(message, owner_id) == "🟢 Ваше сообщение"

        # Обновляем статистику
        update_message_statistics(
            owner_id=owner_id,
            chat_id=message.chat.id,
            is_outgoing=is_outgoing
        )

        # Остальной код обработки сообщения...
        content_type, file_id, caption = get_file_info(message)
        content = message.text if content_type == 'text' else file_id

        messages_log[message.chat.id][message.message_id] = {
            'type': content_type,
            'content': content,
            'timestamp': datetime.now().timestamp(),
            'caption': caption,
            'sender_type': get_sender_type(message, owner_id),
            'chat_title': get_chat_title(message.chat)
        }

    except Exception as e:
        logger.error(f"Error handling message: {str(e)}", exc_info=True)


def update_message_statistics(owner_id: int, chat_id: int, is_outgoing: bool):
    try:
        # Получаем текущую статистику
        stats = supabase.table("message_statistics") \
            .select("*") \
            .eq("user_id", owner_id) \
            .eq("chat_id", chat_id) \
            .execute()

        update_data = {
            "total_messages": 1,
            "outgoing" if is_outgoing else "incoming": 1
        }

        if stats.data:
            existing = stats.data[0]
            update_data = {
                "total_messages": existing['total_messages'] + 1,
                "outgoing": existing['outgoing'] + (1 if is_outgoing else 0),
                "incoming": existing['incoming'] + (0 if is_outgoing else 1)
            }

        # Upsert статистики
        supabase.table("message_statistics").upsert({
            "user_id": owner_id,
            "chat_id": chat_id,
            **update_data
        }, on_conflict="user_id,chat_id").execute()

    except Exception as e:
        logger.error(f"Error updating statistics: {str(e)}")


def create_stats_keyboard(current_page: int, total_pages: int) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    buttons = []

    # Добавляем кнопку "назад"
    buttons.append(InlineKeyboardButton('⬅️', callback_data=f'stats_{current_page-1}' if current_page > 0 else 'none'))
    
    # Добавляем счетчик страниц
    buttons.append(InlineKeyboardButton(f'| {current_page + 1}/{total_pages} |', callback_data='current_page'))
    
    # Добавляем кнопку "вперед"
    buttons.append(InlineKeyboardButton('➡️', callback_data=f'stats_{current_page+1}' if current_page < total_pages - 1 else 'none'))
    
    keyboard.row(*buttons)
    return keyboard

@bot.message_handler(commands=['statistic'])
def handle_statistics(message, page: int = 0):
    try:
        user_id = message.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Неактивированный чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        nopeact = 'неактивированный чат'
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
                f"\n\n<i>Про чаты с названием {nopeact} читать в /help</i>"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Отправляем сообщение с клавиатурой
        bot.send_message(
            message.chat.id,
            '\n'.join(response),
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:
        logger.error(f"Error generating statistics: {str(e)}")
        bot.send_message(message.chat.id, "⚠️ Ошибка получения статистики")

@bot.callback_query_handler(func=lambda call: call.data.startswith('stats_') or call.data in ['none', 'current_page'])
def handle_stats_pagination(call):
    try:
        if call.data == 'none':
            bot.answer_callback_query(call.id, "Больше страниц нет")
            return
        
        if call.data == 'current_page':
            bot.answer_callback_query(call.id, "нахуй ты сюда жмешь?")
            return
            
        page = int(call.data.split('_')[1])
        user_id = call.from_user.id
        response = ["📊 <b>Ваша статистика:</b>\n"]

        # Получаем данные из Supabase
        stats_data = supabase.table("message_statistics") \
            .select("chat_id, total_messages, incoming, outgoing") \
            .eq("user_id", user_id) \
            .execute()

        # Создаем список чатов с их статистикой
        chat_stats = []
        total_all = 0
        incoming_all = 0
        outgoing_all = 0

        for stat in stats_data.data:
            try:
                chat_info = bot.get_chat(stat['chat_id'])
                chat_title = get_chat_title(chat_info)
            except Exception as e:
                chat_title = f"Удалённый чат ({stat['chat_id']})"
                logger.debug(f"Can't get chat info: {str(e)}")

            total_messages = stat['incoming'] + stat['outgoing']
            chat_stats.append({
                'title': chat_title,
                'incoming': stat['incoming'],
                'outgoing': stat['outgoing'],
                'total': total_messages
            })
            
            total_all += stat['total_messages']
            incoming_all += stat['incoming']
            outgoing_all += stat['outgoing']

        # Сортируем чаты по общему количеству сообщений
        chat_stats.sort(key=lambda x: x['total'], reverse=True)

        # Разбиваем на страницы по 6 чатов
        chats_per_page = 6
        total_pages = (len(chat_stats) + chats_per_page - 1) // chats_per_page
        start_idx = page * chats_per_page
        end_idx = start_idx + chats_per_page
        current_page_chats = chat_stats[start_idx:end_idx]

        # Формируем отчет для текущей страницы
        for chat in current_page_chats:
            response.append(
                f"\n👥 <b>Чат:</b> {chat['title']}\n"
                f"• Входящих: {chat['incoming']}\n"
                f"• Исходящих: {chat['outgoing']}\n"
                f"────────────────"
            )

        # Добавляем общую статистику только на первой странице
        if page == 0:
            response.append(
                f"\n<b>Итого по всем чатам:</b>\n"
                f"📥 Входящих: {incoming_all}\n"
                f"📤 Исходящих: {outgoing_all}"
            )

        # Создаем клавиатуру для навигации
        keyboard = create_stats_keyboard(page, total_pages)

        # Редактируем существующее сообщение
        bot.edit_message_text(
            '\n'.join(response),
            call.message.chat.id,
            call.message.message_id,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        
        bot.answer_callback_query(call.id)

    except Exception as e:
        logger.error(f"Error handling stats pagination: {str(e)}")
        bot.answer_callback_query(call.id, "⚠️ Ошибка при переключении страницы")


@bot.edited_business_message_handler(content_types=[
    'text', 'photo', 'video', 'document', 'animation',
    'voice', 'sticker', 'audio', 'location', 'contact'
])
def handle_text_edit(message):
    owner_id = None
    try:
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        old_data = messages_log[message.chat.id].get(message.message_id, {})
        new_content_type, new_file_id, new_caption = get_file_info(message)

        # Формируем текст уведомления
        notification = (
            f"♻️ <b>Изменено сообщение в чате:</b> {old_data.get('chat_title', 'Unknown')}\n"
            f"{old_data.get('sender_type', 'Unknown')}\n"
            f"📂 <b>Тип:</b> {old_data.get('type', 'unknown')}\n"
        )

        # Добавляем старый текст, если это текстовое сообщение
        if old_data.get('type') == 'text':
            notification += f"<b>Было:</b> {escape(old_data.get('content', ''))}\n"
            notification += f"<b>Стало:</b> {escape(message.text)}\n"

        # Если есть старая версия медиа
        if old_data.get('content') and validate_file_id(old_data['content']):
            try:
                media_method = {
                    'photo': bot.send_photo,
                    'video': bot.send_video,
                    'document': bot.send_document,
                    'animation': bot.send_animation,
                    'voice': bot.send_voice,
                    'audio': bot.send_audio,
                    'sticker': bot.send_sticker
                }.get(old_data['type'], bot.send_message)

                # Добавляем старую подпись если есть
                if old_data.get('caption'):
                    notification += f"📌 <b>Исходная подпись:</b> {escape(old_data['caption'])}"

                # Добавляем информацию о новых изменениях
                if new_caption:
                    notification += f"\n✏️ <b>Новая подпись:</b> {escape(new_caption)}"
                elif message.text:
                    notification += f"\n✏️ <b>Новый текст:</b> {escape(message.text)}"

                # Отправляем старое медиа с объединенным уведомлением
                media_method(
                    owner_id,
                    old_data['content'],
                    caption=notification,
                    parse_mode="HTML"
                )

            except Exception as e:
                logger.error(f"Ошибка отправки старого медиа: {str(e)}")
                bot.send_message(owner_id, notification + "\n🚫 <i>Не удалось прикрепить файл</i>")
        else:
            # Если нет старого медиа - отправляем только текст
            bot.send_message(owner_id, notification)

        # Обновляем кеш новой версией
        messages_log[message.chat.id][message.message_id] = {
            'type': new_content_type,
            'content': new_file_id,
            'caption': new_caption,
            'sender_type': old_data.get('sender_type'),
            'chat_title': old_data.get('chat_title'),
            'timestamp': datetime.now().timestamp()
        }

    except Exception as exc:
        logger.error(f"Error handling edit: {str(exc)}", exc_info=True)
        if owner_id:
            error_msg = f"⚠️ Ошибка обработки изменения: {escape(str(exc))}" if exc else "Неизвестная ошибка"
            bot.send_message(owner_id, error_msg)


@bot.deleted_business_messages_handler()
def handle_delete(deleted):
    try:
        bc_id = deleted.business_connection_id
        owner_id = get_connection_owner(bot, bc_id)
        if not owner_id:
            return

        notify_self = get_notify_setting(owner_id)

        for msg_id in deleted.message_ids:
            data = messages_log[deleted.chat.id].pop(msg_id, None)
            if not data:
                continue

            if data.get('sender_type') == "🟢 Ваше сообщение" and not notify_self:
                continue

            notification = (
                f"🗑️ <b>Удалено сообщение в чате:</b> {data.get('chat_title', 'Неизвестный чат')}\n"
                f"{data.get('sender_type', '❓ Неизвестный отправитель')}\n"
                f"📂 <b>Тип:</b> {data['type']}\n"
            )

            try:
                # Для медиа-файлов используем актуальный file_id из кеша
                if data['type'] in ['photo', 'video', 'document', 'animation']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'photo': bot.send_photo,
                        'video': bot.send_video,
                        'document': bot.send_document,
                        'animation': bot.send_animation
                    }[data['type']]

                    if data.get('caption'):
                        notification += f"📌 <b>Подпись:</b> {escape(data['caption'])}\n"

                    send_media(owner_id, file_id, caption=notification)
                    logger.debug(f"Sent media with ID: {file_id}")

                elif data['type'] == 'text':
                    notification += f"📝 <b>Содержимое:</b>\n{escape(data['content'])}"
                    bot.send_message(owner_id, notification)

                elif data['type'] in ['voice', 'audio', 'sticker']:
                    file_id = data.get('content')
                    if not validate_file_id(file_id):
                        raise ValueError("Некорректный идентификатор файла")

                    send_media = {
                        'voice': bot.send_voice,
                        'audio': bot.send_audio,
                        'sticker': bot.send_sticker
                    }[data['type']]
                    send_media(owner_id, file_id)
                    bot.send_message(owner_id, notification)

            except Exception as e:
                logger.error(f"Error processing deleted media {msg_id}: {str(e)}")
                bot.send_message(owner_id, f"⚠️ Не удалось восстановить {data['type']}: {escape(str(e))}")
                # Отправляем текстовую информацию о файле
                bot.send_message(owner_id, notification + f"\n🚫 Идентификатор файла: {file_id}")

    except Exception as e:
        logger.error(f"Error processing delete event: {str(e)}", exc_info=True)


def validate_file_id(file_id: str) -> bool:
    """Улучшенная валидация file_id"""
    try:
        if not isinstance(file_id, str):
            return False
        if len(file_id) < 20 or len(file_id) > 255:
            return False
        return all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_" for c in file_id)
    except:
        return False


@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user = message.from_user
        username = user.username or user.first_name or f"User_{user.id}"
        logger.info(f"Command /start from {user.id} ({username})")

        result = supabase.table("users").select("user_id").eq("user_id", user.id).execute()

        if not result.data:
            logger.info(f"New user registered: {user.id} ({username})")
            if update_user_data(user.id, username):
                active_users.add(user.id)
            else:
                logger.error(f"Failed to register user: {user.id}")

        bot.send_message(message.chat.id, "Инструкция в описании \n<b>Наблюдаю!👀</b>")

    except Exception as e:
        logger.error(f"Error in start_command: {str(e)}", exc_info=True)


@bot.message_handler(commands=['onmy', 'offmy'])
def toggle_notifications(message):
    try:
        user = message.from_user
        # Получаем команду из текста сообщения
        command = message.text.split()[0].lower().replace('/', '')
        new_value = command == 'onmy'

        supabase.table("users").update({"notify_self": new_value}).eq("user_id", user.id).execute()
        status = "включены" if new_value else "отключены"
        logger.info(f"Notifications toggled: {user.id} -> {status}")
        bot.reply_to(message, f"🔔 Уведомления о ваших сообщениях теперь {status}")

    except Exception as e:
        logger.error(f"Error toggling notifications: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при изменении настроек")


@bot.business_connection_handler(func=lambda connection: True)
def handle_business_connection(business_connection):
    try:
        user = business_connection.user
        username = user.username or user.first_name or f"User_{user.id}"

        if business_connection.date > 0:
            logger.info(f"Business connection established: {user.id} ({username})")
            update_user_data(user.id, username, True)
            business_connection_owners[business_connection.id] = user.id
        else:
            logger.info(f"Business connection removed: {user.id} ({username})")
            update_user_data(user.id, username, False)
            if business_connection.id in business_connection_owners:
                del business_connection_owners[business_connection.id]

    except Exception as e:
        logger.error(f"Error handling business connection: {str(e)}", exc_info=True)


def split_message(text: str, max_length: int = 4096) -> list:
    return [text[i:i + max_length] for i in range(0, len(text), max_length)]


@bot.message_handler(commands=['stat'])
def handle_stats(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized stats access attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        logger.info(f"Generating stats for admin {ADMIN_ID}")
        users_data = supabase.table("users").select("*").order("first_seen", desc=True).execute()
        report = ["📊 <b>Статистика</b>\nВсего пользователей: {}".format(len(users_data.data))]

        for user in users_data.data:
            status = "✅ Подключен" if user["is_connected"] else "❌ Отключен"
            report.append(
                f"\n👤 {escape(user['username'])} (ID: {user['user_id']})\n"
                f"Статус: {status}\n"
                f"Первое использование: {user['first_seen']}\n"
                f"Последнее подключение: {user['connection_date'] or 'Нет'}"
            )

        for part in split_message('\n'.join(report)):
            bot.send_message(message.chat.id, part, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating stats: {str(e)}", exc_info=True)
        bot.send_message(message.chat.id, f"⚠️ Ошибка: {escape(str(e))}")


@bot.message_handler(commands=['tell'])
def handle_tell_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            logger.warning(f"Unauthorized tell attempt from {message.from_user.id}")
            bot.reply_to(message, "🚫 Доступ запрещен!")
            return

        admin_states['waiting_for_broadcast'] = True
        bot.reply_to(message, "📢 Отправьте сообщение для рассылки всем пользователям\n"
                            "Поддерживаются текст и фото с подписью\n"
                            "Для отмены используйте команду /stop")
        
    except Exception as e:
        logger.error(f"Error in tell command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка")

@bot.message_handler(commands=['stop'])
def handle_stop_command(message):
    try:
        if message.from_user.id != ADMIN_ID:
            return

        if admin_states.get('waiting_for_broadcast'):
            admin_states['waiting_for_broadcast'] = False
            bot.reply_to(message, "✅ Команда рассылки отменена")
            logger.info(f"Broadcast cancelled by admin")
        
    except Exception as e:
        logger.error(f"Error in stop command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отмене команды")

@bot.message_handler(func=lambda message: message.from_user.id == ADMIN_ID and admin_states.get('waiting_for_broadcast'),
                    content_types=['text', 'photo'])
def handle_broadcast_message(message):
    try:
        admin_states['waiting_for_broadcast'] = False
        
        # Получаем всех пользователей из базы
        users = supabase.table("users").select("user_id").execute()
        
        success_count = 0
        fail_count = 0
        
        for user in users.data:
            try:
                if message.content_type == 'photo':
                    # Для фото берём последнее (самое большое) изображение
                    photo = message.photo[-1].file_id
                    bot.send_photo(user['user_id'], photo, caption=message.caption)
                else:
                    bot.send_message(user['user_id'], message.text)
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to send broadcast to user {user['user_id']}: {str(e)}")
                fail_count += 1
                
        report = (f"📊 Рассылка завершена\n"
                 f"✅ Успешно отправлено: {success_count}\n"
                 f"❌ Ошибок отправки: {fail_count}")
        
        bot.reply_to(message, report)
        logger.info(f"Broadcast completed: {success_count} successful, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Error in broadcast: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при рассылке")


@bot.message_handler(commands=['help'])
def help_command(message):
    try:
        help_text = (
            "🤖 <b>О боте:</b>\n"
            "Этот бот помогает отслеживать сообщения в ваших бизнес-чатах Telegram. "
            "Он уведомляет вас об удалённых и отредактированных сообщениях.\n\n"
            
            "📝 <b>Основные команды:</b>\n"
            "• /start - Запустить бота\n"
            "• /statistic - Показать статистику сообщений\n"
            "• /onmy - Включить уведомления о ваших удалённых сообщениях\n"
            "• /offmy - Отключить уведомления о ваших удалённых сообщениях\n\n"
            
            "⚙️ <b>Настройка:</b>\n"
            "1. Добавьте этого бота в настройках Business аккаунта\n"
            "2. Готово! Бот начнёт отслеживать сообщения\n\n"

            
            "🔒 <b>Безопасность:</b>\n"
            "Бот хранит только метаданные сообщений и не имеет доступа к личной переписке вне бизнес-чатов."

            "\n\n<code>Название чатов с названием неактивированный чат начнут отображатся после того как вы напишите в них любое сообщение</code>"
        )
        
        bot.send_message(message.chat.id, help_text, parse_mode="HTML")
        
    except Exception as e:
        logger.error(f"Error in help command: {str(e)}", exc_info=True)
        bot.reply_to(message, "⚠️ Произошла ошибка при отображении справки")


if __name__ == "__main__":
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Bot crashed: {str(e)}")