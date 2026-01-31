import os
import asyncio
import logging
import urllib.request
import ssl
from telethon import TelegramClient
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ================== ЗАГРУЗКА СЕССИИ ИЗ GITHUB GIST ==================
# ⚠️ ЗАМЕНИТЕ ЭТУ ССЫЛКУ НА ВАШУ СЕКРЕТНУЮ GIST (Raw URL)!
GIST_SESSION_URL = "https://gist.github.com/alekseignatovich-sketch/a1e60714b519f4869c2471711cc86b38.js"

try:
    # Обход SSL-проверки для GitHub (безопасно для публичных Gist)
    context = ssl._create_unverified_context()
    urllib.request.urlretrieve(GIST_SESSION_URL, 'railway_session.session', reporthook=lambda *args: None)
    print("✅ Сессия загружена из GitHub Gist")
except Exception as e:
    print(f"⚠️ Не удалось загрузить сессию: {e}")
    print("💡 Совет: создайте секретный Gist и вставьте Raw URL в переменную GIST_SESSION_URL")

# ================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==================
TOKEN = os.getenv('BOT_TOKEN')
NOTIFY_CHAT_ID = int(os.getenv('YOUR_CHAT_ID'))
API_ID = int(os.getenv('API_ID'))
API_HASH = os.getenv('API_HASH')

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = TelegramClient('railway_session', API_ID, API_HASH)

KEYWORDS = ['telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот', 'разработка', 'скрипт', 'автоматизация', 'freelance', 'заказ', 'проект']
CHANNELS = ['freelansim_ru', 'TGwork', 'partnerkin_job', 'work_on', 'FreeVacanciesIT', 'ru_pythonjobs', 'python_job', 'programming_orders']

async def init_db():
    async with aiosqlite.connect('projects.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (message_id TEXT PRIMARY KEY)')
        await db.commit()

async def check_channels():
    new_projects = []
    async with aiosqlite.connect('projects.db') as db:
        for channel in CHANNELS:
            try:
                messages = await client.get_messages(channel, limit=5)
                for msg in messages:
                    if not msg.text: continue
                    if any(kw in msg.text.lower() for kw in KEYWORDS):
                        msg_id = f"{channel}_{msg.id}"
                        async with db.execute("SELECT 1 FROM sent WHERE message_id=?", (msg_id,)) as cur:
                            if not await cur.fetchone():
                                await db.execute("INSERT INTO sent VALUES (?)", (msg_id,))
                                await db.commit()
                                link = f"https://t.me/{channel}/{msg.id}"
                                text = f"🆕 @{channel}\n\n{msg.text[:250]}...\n\n{link}"
                                new_projects.append(text)
                await asyncio.sleep(3)
            except Exception as e:
                logger.warning(f"⚠️ {channel}: {e}")
    return new_projects

@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("✅ Парсер активен!\n🔍 Мониторинг каналов на заказы по Python/Telegram")

@dp.message(Command("check"))
async def check(message: Message):
    await message.answer("🔍 Проверяю каналы...")
    results = await check_channels()
    if results:
        for msg in results[:3]:
            await message.answer(msg, disable_web_page_preview=False)
        await bot.send_message(NOTIFY_CHAT_ID, f"✅ Найдено {len(results)} новых проектов")
    else:
        await message.answer("📭 Новых проектов не найдено")

async def main():
    logger.info("🚀 Запуск парсера...")
    await init_db()
    
    # Подключаемся к Telegram
    await client.connect()
    
    if not await client.is_user_authorized():
        logger.error("❌ Сессия недействительна! Проверьте:")
        logger.error("1. Правильность ссылки GIST_SESSION_URL")
        logger.error("2. Что файл railway_session.session загружен в Gist")
        logger.error("3. Что сессия не устарела (аккаунт не выходил из системы)")
        return
    
    logger.info("✅ Авторизован через сессию из Gist")
    await bot.send_message(NOTIFY_CHAT_ID, "✅ Парсер запущен и мониторит каналы")
    
    # Первая проверка
    await check_channels()
    
    # Запуск бота
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())
