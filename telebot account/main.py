import telebot
from telebot import types
from telethon import TelegramClient, events
from telethon.tl.types import MessageService, MessageDeleted
from telethon.errors import SessionPasswordNeededError
import logging
from logging.handlers import RotatingFileHandler
from collections import defaultdict
import os
from datetime import datetime
from dotenv import load_dotenv
from html import escape
import asyncio
import threading
import sqlite3
from telebot.apihelper import ApiTelegramException

# Настройка логирования
def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация конфигурации
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = os.getenv("API_ID")  # Получить на https://my.telegram.org/apps
API_HASH = os.getenv("API_HASH")  # Получить на https://my.telegram.org/apps
SESSION_NAME = "telebot_account_session"

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")
if not API_ID:
    raise ValueError("API_ID не найден в переменных окружения!")
if not API_HASH:
    raise ValueError("API_HASH не найден в переменных окружения!")

# Инициализация бота для отправки уведомлений
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# Глобальные переменные
messages_log = defaultdict(dict)  # {chat_id: {message_id: data}}
user_sessions = {}  # {user_id: {'client': TelegramClient, 'phone': str, 'authorized': bool}}
user_states = {}  # {user_id: 'waiting_phone' | 'waiting_code' | 'waiting_password' | 'authorized'}

# Путь к локальной SQLite базе данных
LOCAL_DB_PATH = "telebot_account_messages.db"

def init_local_database():
    """Инициализирует локальную SQLite базу данных для хранения сообщений"""
    try:
        conn = sqlite3.connect(LOCAL_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("DROP TABLE IF EXISTS messages")
        cursor.execute("DROP TABLE IF EXISTS conversations")
        
        cursor.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                sender_type TEXT,
                message_type TEXT NOT NULL,
                content TEXT,
                caption TEXT,
                file_id TEXT,
                timestamp REAL NOT NULL,
                time_formatted TEXT,
                reply_to_message_id INTEGER
            )
        """)
        
        cursor.execute("""
            CREATE TABLE conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                chat_title TEXT,
                last_message_time REAL,
                last_message_type TEXT,
                UNIQUE(chat_id, user_id)
            )
        """)
        
        cursor.execute("CREATE INDEX idx_messages_user_chat ON messages(user_id, chat_id)")
        cursor.execute("CREATE INDEX idx_messages_timestamp ON messages(timestamp)")
        cursor.execute("CREATE INDEX idx_conversations_user ON conversations(user_id)")
        
        conn.commit()
        conn.close()
        logger.info(f"База данных инициализирована: {LOCAL_DB_PATH}")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")

def get_db_connection():
    """Возвращает соединение с локальной базой данных"""
    return sqlite3.connect(LOCAL_DB_PATH)

def safe_send_message(chat_id, text, parse_mode=None, **kwargs):
    """Безопасная отправка сообщения с обработкой ошибки 403 (бот заблокирован)"""
    try:
        return bot.send_message(chat_id, text, parse_mode=parse_mode, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения {chat_id}: {str(e)}")
        raise

def safe_send_photo(chat_id, photo, caption=None, **kwargs):
    """Безопасная отправка фото"""
    try:
        return bot.send_photo(chat_id, photo, caption=caption, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки фото {chat_id}: {str(e)}")
        raise

def safe_send_video(chat_id, video, caption=None, **kwargs):
    """Безопасная отправка видео"""
    try:
        return bot.send_video(chat_id, video, caption=caption, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки видео {chat_id}: {str(e)}")
        raise

def safe_send_document(chat_id, document, caption=None, **kwargs):
    """Безопасная отправка документа"""
    try:
        return bot.send_document(chat_id, document, caption=caption, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки документа {chat_id}: {str(e)}")
        raise

def safe_send_voice(chat_id, voice, **kwargs):
    """Безопасная отправка голосового сообщения"""
    try:
        return bot.send_voice(chat_id, voice, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки голосового сообщения {chat_id}: {str(e)}")
        raise

def safe_send_audio(chat_id, audio, **kwargs):
    """Безопасная отправка аудио"""
    try:
        return bot.send_audio(chat_id, audio, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки аудио {chat_id}: {str(e)}")
        raise

def safe_send_sticker(chat_id, sticker, **kwargs):
    """Безопасная отправка стикера"""
    try:
        return bot.send_sticker(chat_id, sticker, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки стикера {chat_id}: {str(e)}")
        raise

def safe_send_animation(chat_id, animation, caption=None, **kwargs):
    """Безопасная отправка анимации"""
    try:
        return bot.send_animation(chat_id, animation, caption=caption, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки анимации {chat_id}: {str(e)}")
        raise

def safe_send_video_note(chat_id, video_note, **kwargs):
    """Безопасная отправка видеокружка"""
    try:
        return bot.send_video_note(chat_id, video_note, **kwargs)
    except ApiTelegramException as e:
        if e.error_code == 403:
            logger.warning(f"Бот заблокирован пользователем {chat_id}")
            return None
        else:
            raise
    except Exception as e:
        logger.error(f"Ошибка отправки видеокружка {chat_id}: {str(e)}")
        raise

def get_chat_title_from_telethon(chat):
    """Получает название чата из Telethon"""
    try:
        if hasattr(chat, 'title'):
            return escape(chat.title) if chat.title else "Без названия"
        elif hasattr(chat, 'first_name'):
            return escape(chat.first_name or "Приватный чат")
        return "Неизвестный чат"
    except Exception as e:
        logger.error(f"Ошибка получения названия чата: {str(e)}")
        return "Неизвестный чат"

def save_message_to_db(user_id, chat_id, message_id, sender_type, message_type, content, caption, file_id, reply_to_message_id):
    """Сохраняет сообщение в локальную SQLite базу данных"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO messages (
                chat_id, message_id, user_id, sender_type,
                message_type, content, caption, file_id, timestamp, time_formatted, reply_to_message_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            message_id,
            user_id,
            sender_type,
            message_type,
            content,
            caption or '',
            file_id,
            datetime.now().timestamp(),
            datetime.now().strftime('%d.%m.%y %H:%M'),
            reply_to_message_id
        ))
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"Ошибка сохранения в базу данных: {e}")

def get_message_from_db(user_id, chat_id, message_id):
    """Получает сообщение из базы данных"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT sender_type, message_type, content, caption, file_id, reply_to_message_id
            FROM messages
            WHERE user_id = ? AND chat_id = ? AND message_id = ?
        """, (user_id, chat_id, message_id))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'sender_type': result[0],
                'type': result[1],
                'content': result[2],
                'caption': result[3],
                'file_id': result[4],
                'reply_to_message_id': result[5]
            }
        return None
    except Exception as e:
        logger.error(f"Ошибка получения из базы данных: {e}")
        return None

async def setup_telethon_client(user_id, phone):
    """Настраивает и запускает клиент Telethon для пользователя"""
    try:
        session_file = f"{SESSION_NAME}_{user_id}.session"
        client = TelegramClient(session_file, int(API_ID), API_HASH)
        
        await client.connect()
        
        if not await client.is_user_authorized():
            user_states[user_id] = 'waiting_code'
            await client.send_code_request(phone)
            return client, False
        
        user_sessions[user_id] = {
            'client': client,
            'phone': phone,
            'authorized': True
        }
        user_states[user_id] = 'authorized'
        return client, True
        
    except Exception as e:
        logger.error(f"Ошибка настройки клиента Telethon для {user_id}: {str(e)}")
        return None, False

def setup_deleted_messages_handler(client, user_id):
    """Настраивает обработчик удаленных сообщений"""
    
    @client.on(events.MessageDeleted)
    async def handler(event):
        try:
            deleted_ids = event.deleted_ids
            
            for msg_id in deleted_ids:
                # Получаем информацию о чате
                try:
                    chat = await event.get_chat()
                    chat_id = chat.id
                    chat_title = get_chat_title_from_telethon(chat)
                except:
                    # Если не удалось получить чат, пробуем найти в логах
                    chat_id = None
                    chat_title = "Неизвестный чат"
                    for cid, msgs in messages_log.items():
                        if msg_id in msgs:
                            chat_id = cid
                            chat_title = msgs[msg_id].get('chat_title', 'Неизвестный чат')
                            break
                    
                    if not chat_id:
                        continue
                
                # Получаем сохраненное сообщение
                data = None
                if chat_id:
                    data = get_message_from_db(user_id, chat_id, msg_id)
                
                if not data:
                    # Пробуем получить из памяти
                    if chat_id:
                        data = messages_log.get(chat_id, {}).get(msg_id)
                    if not data:
                        continue
                
                # Удаляем из памяти
                if chat_id and chat_id in messages_log and msg_id in messages_log[chat_id]:
                    del messages_log[chat_id][msg_id]
                
                # Формируем уведомление
                reply_info = ""
                if data.get('reply_to_message_id') and chat_id:
                    reply_data = get_message_from_db(user_id, chat_id, data['reply_to_message_id'])
                    if not reply_data:
                        reply_data = messages_log.get(chat_id, {}).get(data['reply_to_message_id'])
                    
                    if reply_data:
                        if reply_data.get('type') == 'text':
                            reply_info = f"\n💬 <b>Ответ на сообщение:</b> {escape(reply_data.get('content', ''))}\n"
                        else:
                            content_types = {
                                'photo': 'фотографию',
                                'video': 'видео',
                                'document': 'документ',
                                'animation': 'анимацию',
                                'voice': 'голосовое сообщение',
                                'audio': 'аудио',
                                'sticker': 'стикер',
                                'video_note': 'кружок',
                                'contact': 'контакт'
                            }
                            reply_info = f"\n💬 <b>Ответ на:</b> {content_types.get(reply_data.get('type'), 'медиафайл')}\n"
                
                notification = (
                    f"🗑️ <b>Удалено сообщение в чате:</b> {chat_title}\n"
                    f"{data.get('sender_type', '❓ Неизвестный отправитель')}\n"
                    f"📂 <b>Тип:</b> {data.get('type', 'Неизвестно')}\n"
                    f"{reply_info}"
                )
                
                # Отправляем уведомление через бота
                if data.get('type') == 'text':
                    content = data.get('content', '')
                    notification += f"📝 <b>Содержимое:</b>\n{escape(content)}"
                    safe_send_message(user_id, notification, parse_mode="HTML")
                else:
                    file_id = data.get('file_id') or data.get('content')
                    if file_id and not (isinstance(file_id, str) and file_id.startswith('[') and file_id.endswith(']')):
                        # Отправляем медиафайл
                        if data.get('type') in ['photo', 'video', 'document', 'animation', 'video_note']:
                            send_func = {
                                'photo': safe_send_photo,
                                'video': safe_send_video,
                                'document': safe_send_document,
                                'animation': safe_send_animation,
                                'video_note': safe_send_video_note
                            }.get(data.get('type'))
                            
                            if send_func:
                                if data.get('caption'):
                                    notification += f"\n📌 <b>Подпись:</b> {escape(data['caption'])}\n"
                                
                                if data.get('type') == 'video_note':
                                    send_func(user_id, file_id)
                                    safe_send_message(user_id, notification, parse_mode="HTML")
                                else:
                                    send_func(user_id, file_id, caption=notification, parse_mode="HTML")
                        elif data.get('type') in ['voice', 'audio', 'sticker']:
                            send_func = {
                                'voice': safe_send_voice,
                                'audio': safe_send_audio,
                                'sticker': safe_send_sticker
                            }.get(data.get('type'))
                            
                            if send_func:
                                send_func(user_id, file_id)
                                safe_send_message(user_id, notification, parse_mode="HTML")
                    else:
                        notification += f"📁 <b>Тип файла:</b> {data.get('type', 'Неизвестно')}"
                        safe_send_message(user_id, notification, parse_mode="HTML")
                        
        except Exception as e:
            logger.error(f"Ошибка обработки удаленного сообщения: {str(e)}", exc_info=True)

def setup_new_messages_handler(client, user_id):
    """Настраивает обработчик новых сообщений"""
    
    @client.on(events.NewMessage)
    async def handler(event):
        try:
            message = event.message
            chat = await event.get_chat()
            chat_id = chat.id
            chat_title = get_chat_title_from_telethon(chat)
            
            # Определяем тип отправителя
            sender_type = "🟢 Ваше сообщение" if message.out else "🔴 Сообщение собеседника"
            
            # Определяем тип сообщения и содержимое
            message_type = 'text'
            content = message.text or ''
            caption = None
            file_id = None
            reply_to_message_id = None
            
            if message.reply_to:
                reply_to_message_id = message.reply_to.reply_to_msg_id
            
            if message.photo:
                message_type = 'photo'
                file_id = f"photo_{message.id}"
            elif message.video:
                message_type = 'video'
                file_id = f"video_{message.id}"
            elif message.document:
                message_type = 'document'
                file_id = f"document_{message.id}"
            elif message.voice:
                message_type = 'voice'
                file_id = f"voice_{message.id}"
            elif message.audio:
                message_type = 'audio'
                file_id = f"audio_{message.id}"
            elif message.sticker:
                message_type = 'sticker'
                file_id = f"sticker_{message.id}"
            elif message.gif:
                message_type = 'animation'
                file_id = f"animation_{message.id}"
            elif message.video_note:
                message_type = 'video_note'
                file_id = f"video_note_{message.id}"
            
            if hasattr(message, 'message') and message.message:
                caption = message.message
            
            # Сохраняем в память
            messages_log[chat_id][message.id] = {
                'type': message_type,
                'content': content if message_type == 'text' else file_id,
                'timestamp': datetime.now().timestamp(),
                'caption': caption,
                'sender_type': sender_type,
                'chat_title': chat_title,
                'reply_to_message_id': reply_to_message_id
            }
            
            # Сохраняем в базу данных
            save_message_to_db(
                user_id, chat_id, message.id, sender_type,
                message_type, content, caption, file_id, reply_to_message_id
            )
            
            # Сохраняем медиафайлы для последующего восстановления
            if message_type != 'text' and message.media:
                try:
                    # Скачиваем медиафайл и сохраняем как file_id для бота
                    media_path = await client.download_media(message, file=f"temp_{user_id}_{message.id}")
                    if media_path:
                        # Отправляем файл боту для получения file_id (в отдельном потоке, так как это синхронный вызов)
                        def save_media_file():
                            try:
                                with open(media_path, 'rb') as f:
                                    sent = None
                                    if message_type == 'photo':
                                        sent = bot.send_photo(user_id, f)
                                    elif message_type == 'video':
                                        sent = bot.send_video(user_id, f, caption=caption)
                                    elif message_type == 'document':
                                        sent = bot.send_document(user_id, f, caption=caption)
                                    elif message_type == 'voice':
                                        sent = bot.send_voice(user_id, f)
                                    elif message_type == 'audio':
                                        sent = bot.send_audio(user_id, f)
                                    elif message_type == 'sticker':
                                        sent = bot.send_sticker(user_id, f)
                                    elif message_type == 'animation':
                                        sent = bot.send_animation(user_id, f, caption=caption)
                                    elif message_type == 'video_note':
                                        sent = bot.send_video_note(user_id, f)
                                    
                                    if sent:
                                        # Получаем file_id
                                        actual_file_id = None
                                        if message_type == 'photo':
                                            actual_file_id = sent.photo[-1].file_id
                                        elif message_type == 'video':
                                            actual_file_id = sent.video.file_id
                                        elif message_type == 'document':
                                            actual_file_id = sent.document.file_id
                                        elif message_type == 'voice':
                                            actual_file_id = sent.voice.file_id
                                        elif message_type == 'audio':
                                            actual_file_id = sent.audio.file_id
                                        elif message_type == 'sticker':
                                            actual_file_id = sent.sticker.file_id
                                        elif message_type == 'animation':
                                            actual_file_id = sent.animation.file_id
                                        elif message_type == 'video_note':
                                            actual_file_id = sent.video_note.file_id
                                        
                                        if actual_file_id:
                                            # Обновляем в памяти и базе данных
                                            messages_log[chat_id][message.id]['content'] = actual_file_id
                                            conn = get_db_connection()
                                            cursor = conn.cursor()
                                            cursor.execute("""
                                                UPDATE messages SET file_id = ? 
                                                WHERE user_id = ? AND chat_id = ? AND message_id = ?
                                            """, (actual_file_id, user_id, chat_id, message.id))
                                            conn.commit()
                                            conn.close()
                                        
                                        # Удаляем отправленное сообщение (чтобы не засорять чат)
                                        try:
                                            bot.delete_message(user_id, sent.message_id)
                                        except:
                                            pass
                                
                                # Удаляем временный файл
                                try:
                                    os.remove(media_path)
                                except:
                                    pass
                            except Exception as e:
                                logger.error(f"Ошибка сохранения медиафайла в потоке: {str(e)}")
                        
                        # Запускаем в отдельном потоке
                        thread = threading.Thread(target=save_media_file, daemon=True)
                        thread.start()
                        
                except Exception as e:
                    logger.error(f"Ошибка сохранения медиафайла: {str(e)}")
                    
        except Exception as e:
            logger.error(f"Ошибка обработки нового сообщения: {str(e)}", exc_info=True)

def run_telethon_client(user_id, client):
    """Запускает клиент Telethon в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def run():
        # Регистрируем обработчики
        setup_new_messages_handler(client, user_id)
        setup_deleted_messages_handler(client, user_id)
        
        # Запускаем клиент
        await client.run_until_disconnected()
    
    loop.run_until_complete(run())

@bot.message_handler(commands=['start'])
def start_command(message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    
    if user_id in user_sessions and user_sessions[user_id].get('authorized'):
        safe_send_message(user_id, "✅ Вы уже авторизованы! Бот отслеживает удаленные сообщения.")
        return
    
    user_states[user_id] = 'waiting_phone'
    safe_send_message(
        user_id,
        "👋 Добро пожаловать!\n\n"
        "Этот бот отслеживает удаленные сообщения в вашем аккаунте Telegram.\n\n"
        "Для начала работы необходимо авторизоваться:\n"
        "1. Отправьте номер телефона в формате +79991234567"
    )

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_phone')
def handle_phone(message):
    """Обработчик ввода номера телефона"""
    user_id = message.from_user.id
    phone = message.text.strip()
    
    if not phone.startswith('+'):
        safe_send_message(user_id, "❌ Номер телефона должен начинаться с + (например, +79991234567)")
        return
    
    # Создаем клиент Telethon
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def auth():
        client, authorized = await setup_telethon_client(user_id, phone)
        if authorized:
            safe_send_message(user_id, "✅ Авторизация успешна! Бот начал отслеживать удаленные сообщения.")
            user_sessions[user_id] = {
                'client': client,
                'phone': phone,
                'authorized': True
            }
            user_states[user_id] = 'authorized'
            
            # Запускаем обработчики в отдельном потоке
            thread = threading.Thread(target=run_telethon_client, args=(user_id, client), daemon=True)
            thread.start()
        else:
            user_sessions[user_id] = {
                'client': client,
                'phone': phone,
                'authorized': False
            }
            safe_send_message(user_id, "📱 Код подтверждения отправлен в Telegram. Отправьте код из SMS:")
    
    loop.run_until_complete(auth())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_code')
def handle_code(message):
    """Обработчик ввода кода из SMS"""
    user_id = message.from_user.id
    code = message.text.strip()
    
    if user_id not in user_sessions:
        safe_send_message(user_id, "❌ Ошибка. Начните заново с команды /start")
        return
    
    client = user_sessions[user_id]['client']
    phone = user_sessions[user_id]['phone']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def sign_in():
        try:
            await client.sign_in(phone, code)
            safe_send_message(user_id, "✅ Авторизация успешна! Бот начал отслеживать удаленные сообщения.")
            user_sessions[user_id]['authorized'] = True
            user_states[user_id] = 'authorized'
            
            # Запускаем обработчики в отдельном потоке
            thread = threading.Thread(target=run_telethon_client, args=(user_id, client), daemon=True)
            thread.start()
        except SessionPasswordNeededError:
            user_states[user_id] = 'waiting_password'
            safe_send_message(user_id, "🔐 Требуется пароль двухфакторной аутентификации. Отправьте пароль:")
        except Exception as e:
            logger.error(f"Ошибка входа: {str(e)}")
            safe_send_message(user_id, f"❌ Ошибка входа: {str(e)}")
    
    loop.run_until_complete(sign_in())

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id) == 'waiting_password')
def handle_password(message):
    """Обработчик ввода пароля 2FA"""
    user_id = message.from_user.id
    password = message.text.strip()
    
    if user_id not in user_sessions:
        safe_send_message(user_id, "❌ Ошибка. Начните заново с команды /start")
        return
    
    client = user_sessions[user_id]['client']
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def sign_in():
        try:
            await client.sign_in(password=password)
            safe_send_message(user_id, "✅ Авторизация успешна! Бот начал отслеживать удаленные сообщения.")
            user_sessions[user_id]['authorized'] = True
            user_states[user_id] = 'authorized'
            
            # Запускаем обработчики в отдельном потоке
            thread = threading.Thread(target=run_telethon_client, args=(user_id, client), daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Ошибка входа с паролем: {str(e)}")
            safe_send_message(user_id, f"❌ Ошибка входа: {str(e)}")
    
    loop.run_until_complete(sign_in())

@bot.message_handler(commands=['status'])
def status_command(message):
    """Проверка статуса авторизации"""
    user_id = message.from_user.id
    
    if user_id in user_sessions and user_sessions[user_id].get('authorized'):
        safe_send_message(user_id, "✅ Бот активен и отслеживает удаленные сообщения.")
    else:
        safe_send_message(user_id, "❌ Бот не авторизован. Используйте /start для авторизации.")

@bot.message_handler(commands=['help'])
def help_command(message):
    """Справка по использованию бота"""
    help_text = (
        "📖 <b>Справка по использованию бота</b>\n\n"
        "Этот бот отслеживает удаленные сообщения в вашем аккаунте Telegram.\n\n"
        "<b>Команды:</b>\n"
        "/start - Начать авторизацию\n"
        "/status - Проверить статус бота\n"
        "/help - Показать эту справку\n\n"
        "<b>Как это работает:</b>\n"
        "1. Авторизуйтесь через номер телефона и код из SMS\n"
        "2. Бот начнет отслеживать все сообщения в вашем аккаунте\n"
        "3. При удалении сообщения вы получите уведомление с его содержимым"
    )
    safe_send_message(message.from_user.id, help_text)

if __name__ == "__main__":
    # Инициализируем базу данных
    init_local_database()
    
    logger.info("Бот запущен!")
    bot.polling(none_stop=True)

