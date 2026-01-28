# Freelance Parser Bot

Telegram-бот, который парсит свежие проекты с бирж фриланса (FL.ru, Kwork и др.) и присылает уведомления по ключевым словам (telegram bot, python, parser и т.д.).

## Как запустить локально

1. `pip install -r requirements.txt`
2. Замени TOKEN и YOUR_CHAT_ID в main.py
3. `python main.py`

## Деплой на Railway.app

1. Создай репозиторий на GitHub с этими файлами
2. На railway.app → New Project → Deploy from GitHub
3. Добавь переменные окружения: TOKEN, YOUR_CHAT_ID
4. Start Command: `python main.py`

## Важно

- Селекторы HTML бирж часто меняются — проверяй в браузере (F12) и обновляй в коде.
- Добавляй задержки / прокси, если банят по IP.
- Для большего количества бирж — расширяй функции parse_...

Удачи с заказами!
