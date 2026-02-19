# Инструкция по деплою

## Что заливать на GitHub

Заливайте **всю папку `deploy/`** на GitHub. Это готовый к деплою проект.

## Структура папки deploy:

```
deploy/
├── api_server.py          # Flask приложение
├── backapp.py             # Модуль с бизнес-логикой (скопируйте из Working 05.08.25/)
├── referral.py            # Модуль реферальной системы
├── invis_web_static/
│   └── index.html         # Статический HTML файл
├── Procfile               # Конфигурация для Railway/Render
├── runtime.txt            # Версия Python
├── requirements.txt       # Зависимости Python
└── README.md             # Этот файл
```

## ⚠️ ВАЖНО: Скопируйте backapp.py

Файл `backapp.py` слишком большой для автоматического копирования. 

**Вручную скопируйте файл:**
- Из: `Working 05.08.25/backapp.py`
- В: `deploy/backapp.py`

## Деплой на Railway

1. Создайте репозиторий на GitHub
2. Загрузите всю папку `deploy/` в корень репозитория
3. На Railway создайте новый проект из GitHub репозитория
4. Добавьте переменные окружения из `ton.env`
5. Railway автоматически задеплоит проект

## Деплой на Render

1. Создайте репозиторий на GitHub  
2. Загрузите всю папку `deploy/` в корень репозитория
3. На Render создайте Web Service из GitHub репозитория
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn api_server:app --bind 0.0.0.0:$PORT`
6. Добавьте переменные окружения

Подробная инструкция в файле DEPLOY.md (если он есть в папке deploy)
