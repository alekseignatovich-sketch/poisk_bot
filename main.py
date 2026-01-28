import asyncio
import logging
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
TOKEN = 'YOUR_BOT_TOKEN_HERE'           # ← замени на свой от @BotFather
YOUR_CHAT_ID = 123456789                # ← твой Telegram ID (узнай через @getmyid_bot)
KEYWORDS = ['telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот', 'разработка']  # добавляй свои

ua = UserAgent()
DB_FILE = 'projects.db'

# ================== БАЗА ДАННЫХ ==================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (link TEXT PRIMARY KEY)')
        await db.commit()

# ================== ПАРСЕРЫ (селекторы — проверь в браузере F12, они могут меняться!) ==================
async def parse_fl_ru():
    url = 'https://www.fl.ru/projects/?kind=5'
    headers = {'User-Agent': ua.random}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Актуальные селекторы на 2026 (проверь! часто меняются)
        projects = soup.select('div.b-post')  # или 'div.project-item', 'article.project'
        new_projects = []
        
        async with aiosqlite.connect(DB_FILE) as db:
            for proj in projects[:8]:  # берём свежие
                title_tag = proj.select_one('a.b-post__link, a.project-title, h2 a')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                link = 'https://www.fl.ru' + title_tag['href'] if title_tag['href'].startswith('/') else title_tag['href']
                
                desc_tag = proj.select_one('div.b-post__txt, div.description, p')
                desc = desc_tag.get_text(strip=True)[:250] if desc_tag else ''
                
                text = (title + ' ' + desc).lower()
                if any(kw.lower() in text for kw in KEYWORDS):
                    async with db.execute("SELECT link FROM sent WHERE link = ?", (link,)) as cursor:
                        if await cursor.fetchone() is None:
                            await db.execute("INSERT INTO sent (link) VALUES (?)", (link,))
                            await db.commit()
                            new_projects.append(f"**FL.ru**\n{title}\n{link}\n{desc[:150]}...")
        return new_projects
    except Exception as e:
        logging.error(f"FL.ru error: {e}")
        return []

async def parse_kwork():
    url = 'https://kwork.ru/projects?c=41'  # категория "Скрипты и боты"
    headers = {'User-Agent': ua.random}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        cards = soup.select('div.want-card, div.project-card, div.wants__item')
        new_projects = []
        
        async with aiosqlite.connect(DB_FILE) as db:
            for card in cards[:8]:
                title_tag = card.select_one('h3.wants-card__header-title a, a.want__title')
                if not title_tag:
                    continue
                title = title_tag.get_text(strip=True)
                link = 'https://kwork.ru' + title_tag['href'] if title_tag['href'].startswith('/') else title_tag['href']
                
                desc_tag = card.select_one('div.wants-card__description, div.want__desc')
                desc = desc_tag.get_text(strip=True)[:250] if desc_tag else ''
                
                text = (title + ' ' + desc).lower()
                if any(kw.lower() in text for kw in KEYWORDS):
                    async with db.execute("SELECT link FROM sent WHERE link = ?", (link,)) as cursor:
                        if await cursor.fetchone() is None:
                            await db.execute("INSERT INTO sent (link) VALUES (?)", (link,))
                            await db.commit()
                            new_projects.append(f"**Kwork**\n{title}\n{link}\n{desc[:150]}...")
        return new_projects
    except Exception as e:
        logging.error(f"Kwork error: {e}")
        return []

# Добавь аналогично другие биржи: Freelance.ru, Weblancer.net и т.д.
# Пример для Freelance.ru (адаптируй селекторы)
async def parse_freelance_ru():
    url = 'https://www.freelance.ru/projects'
    # ... аналогичный код, селекторы: div.project, a.title и т.д.
    return []  # пока заглушка — реализуй сам по аналогии

# ================== ШЕДУЛЕР + БОТ ==================
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=12)  # каждые 12 мин, чтобы не блочило
async def check_all():
    results = []
    results += await parse_fl_ru()
    results += await parse_kwork()
    # results += await parse_freelance_ru()  # и другие
    
    for msg in results:
        try:
            await bot.send_message(YOUR_CHAT_ID, msg, disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"Send error: {e}")

# Команды для управления
@dp.message(Command("start"))
async def start(message: Message):
    await message.answer("Бот запущен! Я ищу заказы по ключам: " + ", ".join(KEYWORDS))

@dp.message(Command("keywords"))
async def show_keywords(message: Message):
    await message.answer("Текущие ключи:\n" + "\n".join(KEYWORDS))

# ================== ЗАПУСК ==================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    await bot.send_message(YOUR_CHAT_ID, "Парсер фриланс-бирж запущен! Ожидаю новые проекты...")
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
