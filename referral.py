import logging
from datetime import datetime, timedelta
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Настройка логирования
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv('ton.env')

# Инициализация Supabase
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def generate_referral_link(user_id: int) -> str:
    """Генерирует реферальную ссылку для пользователя"""
    try:
        # Проверяем существование пользователя
        user = supabase.table("users").select("user_id").eq("user_id", user_id).execute()
        if not user.data:
            logger.error(f"User {user_id} not found")
            return None

        # Создаем реферальную ссылку
        bot_username = os.getenv("BOT_USERNAME", "your_bot_username")
        return f"https://t.me/{bot_username}?start=ref_{user_id}"

    except Exception as e:
        logger.error(f"Error generating referral link: {str(e)}")
        return None

def process_referral(user_id: int, referrer_id: int) -> bool:
    """Обрабатывает реферальную связь между пользователями"""
    try:
        # Проверяем, что пользователь не является своим рефералом
        if user_id == referrer_id:
            return False

        # Проверяем существование обоих пользователей
        users = supabase.table("users").select("user_id").in_("user_id", [user_id, referrer_id]).execute()
        if len(users.data) != 2:
            return False

        # Проверяем, не является ли пользователь уже чьим-то рефералом
        existing = supabase.table("referrals").select("user_id").eq("user_id", user_id).execute()
        if existing.data:
            return False

        # Создаем реферальную связь
        referral_data = {
            "user_id": user_id,
            "referrer_id": referrer_id,
            "created_at": datetime.now().isoformat(),
            "is_active": False
        }

        result = supabase.table("referrals").insert(referral_data).execute()
        return bool(result.data)

    except Exception as e:
        logger.error(f"Error processing referral: {str(e)}")
        return False

def activate_referral_bonus(user_id: int) -> bool:
    """Активирует бонус для реферера при активации подписки рефералом"""
    try:
        # Получаем информацию о реферале
        referral = supabase.table("referrals").select("*").eq("user_id", user_id).execute()
        if not referral.data:
            return False

        referral_info = referral.data[0]
        if referral_info["is_active"]:
            return False

        # Получаем текущую подписку реферера
        subscription = supabase.table("subscriptions").select("*").eq("user_id", referral_info["referrer_id"]).execute()
        
        # Рассчитываем новую дату окончания подписки
        if subscription.data:
            current_end = datetime.fromisoformat(subscription.data[0]["end_date"])
            new_end = current_end + timedelta(days=7)
        else:
            new_end = datetime.now() + timedelta(days=7)

        # Ручной upsert: сначала update, если не обновилось — insert
        update_result = supabase.table("subscriptions").update({
            "subscription_type": "referral",
            "start_date": datetime.now().isoformat(),
            "end_date": new_end.isoformat(),
            "payment_id": "referral_bonus"
        }).eq("user_id", referral_info["referrer_id"]).execute()

        if not update_result.data:
            supabase.table("subscriptions").insert({
                "user_id": referral_info["referrer_id"],
                "subscription_type": "referral",
                "start_date": datetime.now().isoformat(),
                "end_date": new_end.isoformat(),
                "payment_id": "referral_bonus"
            }).execute()

        # Отмечаем реферала как активного
        supabase.table("referrals").update({"is_active": True}).eq("user_id", user_id).execute()
        return True

    except Exception as e:
        logger.error(f"Error activating referral bonus: {str(e)}")
        return False

def get_referral_stats(user_id: int) -> dict:
    """Получает статистику рефералов пользователя"""
    try:
        # Получаем всех рефералов пользователя
        referrals = supabase.table("referrals").select("*").eq("referrer_id", user_id).execute()
        
        # Получаем активных рефералов (с подпиской)
        active_referrals = supabase.table("referrals") \
            .select("*") \
            .eq("referrer_id", user_id) \
            .eq("is_active", True) \
            .execute()

        return {
            "total_referrals": len(referrals.data),
            "active_referrals": len(active_referrals.data),
            "days_earned": len(active_referrals.data) * 7  # 7 дней за каждого активного реферала
        }

    except Exception as e:
        logger.error(f"Error getting referral stats: {str(e)}")
        return {
            "total_referrals": 0,
            "active_referrals": 0,
            "days_earned": 0
        }

def get_user_profile(user_id: int) -> dict:
    """Получает информацию профиля пользователя"""
    try:
        # Получаем основную информацию о пользователе
        user_info = supabase.table("users").select("*").eq("user_id", user_id).execute()
        if not user_info.data:
            return None
            
        # Получаем информацию о подписке
        subscription = supabase.table("subscriptions") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("is_active", True) \
            .execute()
            
        # Получаем статистику рефералов
        referral_stats = get_referral_stats(user_id)
        
        return {
            "user": user_info.data[0],
            "subscription": subscription.data[0] if subscription.data else None,
            "referral_stats": referral_stats
        }
    except Exception as e:
        logger.error(f"Error getting user profile: {str(e)}")
        return None
