import os
from flask import Flask, request, jsonify, send_from_directory, Response
from backapp import (
    _verify_telegram_login,
    get_connection_id_by_owner,
    _create_owner_token,
    _verify_owner_token,
    get_db_connection,
    send_message_as_owner,
    init_local_database,
    bot,
)

# Настройка статической папки
_static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "invis_web_static")
app = Flask(__name__, static_folder=_static, static_url_path="")

# Получаем username бота для виджета Telegram
_bot_username = None

def get_bot_username():
    global _bot_username
    if _bot_username is None:
        try:
            me = bot.get_me()
            _bot_username = me.username or ""
        except Exception:
            _bot_username = os.getenv("BOT_USERNAME", "")
    return _bot_username

# Раздача главной страницы
@app.route("/")
def index():
    try:
        with open(os.path.join(_static, "index.html"), "r", encoding="utf-8") as f:
            html = f.read()
        bot_name = get_bot_username() or "YourBot"
        html = html.replace("__BOT_USERNAME__", bot_name)
        return Response(html, mimetype="text/html; charset=utf-8")
    except Exception as e:
        return send_from_directory(_static, "index.html")

# Разрешаем запросы с любого домена (для деплоя на хостинг)
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
    else:
        response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/api/auth", methods=["POST", "OPTIONS"])
def api_auth():
    if request.method == "OPTIONS":
        return ("", 204)
    data = request.get_json() or {}
    user_id = _verify_telegram_login(dict(data))
    if user_id is None:
        return jsonify({"ok": False, "error": "invalid_auth"}), 401
    if get_connection_id_by_owner(user_id) is None:
        return jsonify({"ok": False, "error": "no_business_connection"}), 403
    token = _create_owner_token(user_id)
    return jsonify({"ok": True, "token": token, "owner_id": user_id})


@app.route("/api/chats", methods=["GET", "OPTIONS"])
def api_chats():
    if request.method == "OPTIONS":
        return ("", 204)
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    owner_id = _verify_owner_token(token)
    if owner_id is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT chat_id, chat_title, last_message_time, last_message_type
        FROM conversations WHERE owner_id = ?
        ORDER BY last_message_time DESC
        """,
        (owner_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    chats = [
        {
            "chat_id": r[0],
            "chat_title": r[1] or f"Чат {r[0]}",
            "last_message_time": r[2],
            "last_message_type": r[3] or "text",
        }
        for r in rows
    ]
    return jsonify({"ok": True, "chats": chats})


@app.route("/api/chats/<int:chat_id>/messages", methods=["GET", "OPTIONS"])
def api_chat_messages(chat_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    owner_id = _verify_owner_token(token)
    if owner_id is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, message_id, sender_type, message_type, content, caption,
               file_id, timestamp, time_formatted, reply_to_message_id
        FROM messages
        WHERE owner_id = ? AND chat_id = ?
        ORDER BY timestamp ASC
        """,
        (owner_id, chat_id),
    )
    rows = cursor.fetchall()
    conn.close()

    messages = [
        {
            "id": r[0],
            "message_id": r[1],
            "sender_type": r[2],
            "message_type": r[3],
            "content": r[4] or "",
            "caption": r[5] or "",
            "file_id": r[6],
            "timestamp": r[7],
            "time_formatted": r[8],
            "reply_to_message_id": r[9],
        }
        for r in rows
    ]
    return jsonify({"ok": True, "messages": messages})


@app.route("/api/chats/<int:chat_id>/send", methods=["POST", "OPTIONS"])
def api_chat_send(chat_id):
    if request.method == "OPTIONS":
        return ("", 204)
    token = request.headers.get("Authorization", "").replace("Bearer ", "").strip()
    owner_id = _verify_owner_token(token)
    if owner_id is None:
        return jsonify({"ok": False, "error": "unauthorized"}), 401

    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"ok": False, "error": "empty_text"}), 400

    if send_message_as_owner(owner_id, chat_id, text):
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "send_failed"}), 500


if __name__ == "__main__":
    # чтобы база и всё остальное инициализировалось так же, как в backapp.py
    init_local_database()
    # Railway использует переменную PORT, локально можно использовать INVIS_WEB_PORT
    port = int(os.getenv("PORT", os.getenv("INVIS_WEB_PORT", "5000")))
    app.run(host="0.0.0.0", port=port, threaded=True)
