import telebot
import logging
from datetime import datetime
from html import escape
from collections import defaultdict

logger = logging.getLogger(__name__)

# Глобальные переменные для трекинга
messages_log = defaultdict(dict)
business_connection_owners = {}

def get_connection_owner(bot, supabase, connection_id: str) -> int:
    try:
        if connection_id in business_connection_owners:
            return business_connection_owners[connection_id]

        # ... остальной код функции ...

def get_file_info(message):
    content_type = message.content_type
    file_id = None
    caption = getattr(message, 'caption', None)
    
    # ... остальной код функции ...

def handle_message(bot, supabase, message):
    try:
        logger.debug(f"Raw message data: {message.json}")
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, supabase, bc_id)
        
        # ... остальной код функции ...

def handle_text_edit(bot, supabase, message):
    owner_id = None
    try:
        bc_id = message.business_connection_id
        owner_id = get_connection_owner(bot, supabase, bc_id)
        
        # ... остальной код функции ...

def handle_delete(bot, supabase, deleted):
    try:
        bc_id = deleted.business_connection_id
        owner_id = get_connection_owner(bot, supabase, bc_id)
        
        # ... остальной код функции ...
