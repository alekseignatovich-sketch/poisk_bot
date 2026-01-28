import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from bs4 import BeautifulSoup
import requests
from fake_useragent import UserAgent
import aiosqlite
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import random

# ================== НАСТРОЙКИ ==================
TOKEN = '8244939586:AAFliEkZin4YSJiZy5Bn2w39jqlUqMsq5wo'           # ← ТОЛЬКО НОВЫЙ ТОКЕН после пересоздания бота!!!
YOUR_CHAT_ID = 1300197924               # ← ТВОЙ chat ID (положительное число)

KEYWORDS = [
    'telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот',
    'разработка', 'скрипт', 'автоматизация', 'freelance'
]  # добавляй/убирай свои ключевые слова

ua = UserAgent()
DB_FILE = 'projects.db'
CHECK_INTERVAL_MIN = 15  # каждые 15 минут — оптимально для Railway

# ================== ИНИЦИАЛИЗАЦИЯ БД ==================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (link TEXT PRIMARY KEY)')
        await db.commit()

# ================== ПАРСЕРЫ ==================
async def parse_fl_ru():
    url = 'https://www.fl.ru/projects/?kind=5'
    headers = {'User-Agent': ua.random}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Гибкие селекторы (несколько вариантов)
        projects = soup.select('div.b-post, div.project-item, article.project, div.b-layout__project')
        new_projects = []
        
        async with aiosqlite.connect(DB_FILE) as db:
            for proj in projects[:10]:
                title_tag = proj.select_one('a.b-post__link, a.project-title, h2 a, .title a')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag['href']
                link = 'https://www.fl.ru' + href if href.startswith('/') else href
                
                desc_tag = proj.select_one('div.b-post__txt, div.description, p, .descr')
                desc = desc_tag.get_text(strip=True)[:300] if desc_tag else ''
                
                text = (title + ' ' + desc).lower()
                if any(kw.lower() in text for kw in KEYWORDS):
                    async with db.execute("SELECT link FROM sent WHERE link = ?", (link,)) as cursor:
                        if await cursor.fetchone() is None:
                            await db.execute("INSERT INTO sent (link) VALUES (?)", (link,))
                            await db.commit()
                            new_projects.append(f"**FL.ru** | {title}\n{link}\n{desc[:200]}...")
        return new_projects
    except Exception as e:
        logging.error(f"FL.ru parse error: {e}")
        return []

async def parse_kwork():
    url = 'https://kwork.ru/projects?c=41'
    headers = {'User-Agent': ua.random}
    try:
        r = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        cards = soup.select('div.want-card, div.project-card, div.wants__item, .card')
        new_projects = []
        
        async with aiosqlite.connect(DB_FILE) as db:
            for card in cards[:10]:
                title_tag = card.select_one('h3 a, a.want__title, .title a')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                href = title_tag['href']
                link = 'https://kwork.ru' + href if href.startswith('/') else href
                
                desc_tag = card.select_one('div.wants-card__description, div.want__desc, .description')
                desc = desc_tag.get_text(strip=True)[:300] if desc_tag else ''
                
                text = (title + ' ' + desc).lower()
                if any(kw.lower() in text for kw in KEYWORDS):
                    async with db.execute("SELECT link FROM sent WHERE link = ?", (link,)) as cursor:
                        if await cursor.fetchone() is None:
                            await db.execute("INSERT INTO sent (link) VALUES (?)", (link,))
                            await db.commit()
                            new_projects.append(f"**Kwork** | {title}\n{link}\n{desc[:200]}...")
        return new_projects
    except Exception as e:
        logging.error(f"Kwork parse error: {e}")
        return []

# ================== ШЕДУЛЕР И БОТ ==================
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=CHECK_INTERVAL_MIN)
async def check_all():
    logging.info(f"Проверка бирж начата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results = []
    results += await parse_fl_ru()
    results += await parse_kwork()
    # results += await parse_freelance_ru()  # добавь когда будешь готов
    
    for msg in results:
        try:
            await bot.send_message(YOUR_CHAT_ID, msg, disable_web_page_preview=True)
            logging.info(f"Отправлено: {msg[:50]}...")
        except Exception as e:
            logging.error(f"Ошибка отправки: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Парсер запущен!\n"
        f"Ключевые слова: {', '.join(KEYWORDS)}\n"
        "Буду присылать новые заказы каждые 15 минут."
    )

@dp.message(Command("status"))
async def status(message: Message):
    await message.answer("Бот работает. Последняя проверка: скоро...")

# ================== ЗАПУСК ==================
async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    await init_db()
    
    try:
        await bot.send_message(YOUR_CHAT_ID, "Парсер фриланс-бирж запущен! Ожидаю новые проекты...")
        logging.info("Стартовое сообщение отправлено")
    except Exception as e:
        logging.warning(f"Не удалось отправить стартовое сообщение: {e} (возможно, нужно /start боту)")

    scheduler.start()
    logging.info("Scheduler запущен. Интервал: 15 мин")

    # Polling (текущий режим)
    await dp.start_polling(bot, skip_updates=True)

    # Если хочешь перейти на webhook (рекомендую для Railway):
    # await dp.start_webhook(
    #     webhook_path=f"/webhook/{TOKEN}",
    #     webhook_url="https://твой-домен.up.railway.app/webhook",
    #     skip_updates=True
    # )

if __name__ == '__main__':
    asyncio.run(main())
