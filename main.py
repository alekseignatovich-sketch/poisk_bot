import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, events
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== НАСТРОЙКИ ==================
TOKEN = 'YOUR_BOT_TOKEN_HERE'  # Токен твоего Telegram-бота (для отправки тебе уведомлений)
YOUR_CHAT_ID = 123456789       # Твой chat ID

API_ID = 1234567               # Твой API ID с my.telegram.org
API_HASH = 'your_api_hash_here'  # Твой API HASH
PHONE = '+1234567890'          # Твой номер TG (для userbot)

KEYWORDS = [
    'telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот',
    'разработка', 'скрипт', 'автоматизация', 'freelance', 'заказ', 'проект'
]

CHANNELS = [  # Список каналов/чатов (usernames без @)
    'freelansim_ru', 'TGwork', 'partnerkin_job', 'work_on', 'FreeVacanciesIT',
    'ru_pythonjobs', 'python_job', 'programming_orders', 'habr_career', 'get_it_jobs',
    'pro_jvm_jobs', 'data_science_jobs', 'webfrl', 'distantsiya', 'udalenka_chat'
]

DB_FILE = 'projects.db'
CHECK_INTERVAL_MIN = 15

# ================== ИНИЦИАЛИЗАЦИЯ БД ==================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (message_id TEXT PRIMARY KEY)')
        await db.commit()

# ================== USERBOT ДЛЯ МОНИТОРИНГА ==================
client = TelegramClient('userbot_session', API_ID, API_HASH)

async def check_channels():
    logging.info(f"Проверка каналов: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    new_projects = []
    async with aiosqlite.connect(DB_FILE) as db:
        for channel_username in CHANNELS:
            try:
                entity = await client.get_entity(channel_username)
                messages = await client.get_messages(entity, limit=10)  # Последние 10 сообщений
                for msg in messages:
                    if msg.text:
                        text = msg.text.lower()
                        msg_id = f"{channel_username}_{msg.id}"
                        if any(kw.lower() in text for kw in KEYWORDS):
                            async with db.execute("SELECT message_id FROM sent WHERE message_id=?", (msg_id,)) as cursor:
                                if await cursor.fetchone() is None:
                                    await db.execute("INSERT INTO sent (message_id) VALUES (?)", (msg_id,))
                                    await db.commit()
                                    link = f"https://t.me/{channel_username}/{msg.id}"
                                    new_projects.append(f"**{channel_username}** | {text[:200]}...\n{link}")
                await asyncio.sleep(2)  # Задержка, чтобы не банили
            except Exception as e:
                logging.error(f"Ошибка в {channel_username}: {e}")
    return new_projects

# ================== ШЕДУЛЕР И БОТ ДЛЯ УВЕДОМЛЕНИЙ ==================
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=CHECK_INTERVAL_MIN)
async def check_all():
    results = await check_channels()
    for msg in results:
        try:
            await bot.send_message(YOUR_CHAT_ID, msg, disable_web_page_preview=True)
            logging.info(f"Отправлено: {msg[:50]}...")
        except Exception as e:
            logging.error(f"Send error: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(f"Парсер TG-каналов запущен!\nКлючи: {', '.join(KEYWORDS)}\nПроверяю каждые {CHECK_INTERVAL_MIN} мин.")

@dp.message(Command("status"))
async def status(message: Message):
    await message.answer("Бот онлайн. Ждём новые заказы...")

# ================== ЗАПУСК ==================
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    await init_db()
    await client.start(phone=PHONE)  # Авторизация userbot (введи код из TG один раз)
    try:
        await bot.send_message(YOUR_CHAT_ID, "Парсер TG-каналов запущен! Ожидаю проекты...")
        logging.info("Стартовое сообщение отправлено")
    except Exception as e:
        logging.warning(f"Стартовое не ушло: {e}")

    scheduler.start()
    logging.info(f"Scheduler запущен. Интервал: {CHECK_INTERVAL_MIN} мин")

    await dp.start_polling(bot, skip_updates=True)
    await client.run_until_disconnected()

if __name__ == '__main__':
    asyncio.run(main())
