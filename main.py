import os
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==================
TOKEN = os.getenv('BOT_TOKEN')
YOUR_CHAT_ID = int(os.getenv('YOUR_CHAT_ID', '0'))
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')

# Проверка обязательных переменных
if not all([TOKEN, YOUR_CHAT_ID, API_ID, API_HASH, PHONE]):
    missing = [k for k, v in {
        'BOT_TOKEN': TOKEN,
        'YOUR_CHAT_ID': YOUR_CHAT_ID if YOUR_CHAT_ID else None,
        'API_ID': API_ID if API_ID else None,
        'API_HASH': API_HASH,
        'PHONE': PHONE
    }.items() if not v]
    raise RuntimeError(
        f"❌ Отсутствуют переменные окружения: {', '.join(missing)}\n"
        "Настройте их в Railway: Project Settings → Variables"
    )

# ================== НАСТРОЙКИ ПАРСЕРА ==================
KEYWORDS = [
    'telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот',
    'разработка', 'скрипт', 'автоматизация', 'freelance', 'заказ', 'проект',
    'программирование', 'backend', 'frontend', 'api', 'django', 'fastapi'
]

CHANNELS = [
    'freelansim_ru', 'TGwork', 'partnerkin_job', 'work_on', 'FreeVacanciesIT',
    'ru_pythonjobs', 'python_job', 'programming_orders', 'habr_career', 'get_it_jobs',
    'pro_jvm_jobs', 'data_science_jobs', 'webfrl', 'distantsiya', 'udalenka_chat',
    'tgram_jobs', 'tgdev_jobs', 'it_vacancies', 'remote_jobs_ru'
]

DB_FILE = 'projects.db'
CHECK_INTERVAL_MIN = 15

# ================== НАСТРОЙКА ЛОГИРОВАНИЯ ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ==================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sent (
                message_id TEXT PRIMARY KEY,
                channel TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON sent(timestamp)')
        await db.commit()
    logger.info("✅ База данных инициализирована")

# ================== ФУНКЦИЯ АВТОРИЗАЦИИ ==================
async def authorize(client):
    """Авторизация с поддержкой 2FA"""
    if await client.is_user_authorized():
        logger.info("✅ Уже авторизован в Telegram")
        return

    logger.info("📱 Требуется авторизация в Telegram...")
    try:
        await client.send_code_request(PHONE)
        logger.info("📤 Код подтверждения отправлен в Telegram")
        
        # Запрос кода через консоль
        code = input("🔑 Введите код из Telegram (5 цифр): ")
        try:
            await client.sign_in(PHONE, code)
        except SessionPasswordNeededError:
            password = input("🔐 Введите пароль 2FA: ")
            await client.sign_in(password=password)
        
        logger.info("✅ Авторизация успешна!")
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        raise

# ================== USERBOT ДЛЯ МОНИТОРИНГА КАНАЛОВ ==================
client = TelegramClient('railway_session', API_ID, API_HASH)

async def check_channels():
    """Проверка каналов на новые проекты"""
    logger.info(f"🔍 Проверка {len(CHANNELS)} каналов...")
    new_projects = []
    
    async with aiosqlite.connect(DB_FILE) as db:
        for channel_username in CHANNELS:
            try:
                # Получаем entity канала
                entity = await client.get_entity(channel_username)
                messages = await client.get_messages(entity, limit=5)  # Только 5 последних
                
                for msg in messages:
                    if not msg.text:
                        continue
                    
                    text_lower = msg.text.lower()
                    msg_id = f"{channel_username}_{msg.id}"
                    
                    # Проверяем ключевые слова
                    if any(kw.lower() in text_lower for kw in KEYWORDS):
                        # Проверяем, не отправляли ли уже
                        async with db.execute("SELECT 1 FROM sent WHERE message_id=?", (msg_id,)) as cursor:
                            if await cursor.fetchone() is None:
                                # Сохраняем в БД
                                await db.execute(
                                    "INSERT INTO sent (message_id, channel) VALUES (?, ?)",
                                    (msg_id, channel_username)
                                )
                                await db.commit()
                                
                                # Формируем ссылку БЕЗ пробелов (критическая ошибка исправлена!)
                                link = f"https://t.me/{channel_username}/{msg.id}"
                                
                                # Формируем сообщение
                                preview = msg.text[:250] + "..." if len(msg.text) > 250 else msg.text
                                message = (
                                    f"🆕 Новый проект в @{channel_username}\n\n"
                                    f"{preview}\n\n"
                                    f"🔗 {link}"
                                )
                                new_projects.append(message)
                
                # Задержка между каналами (защита от флуда)
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка при проверке @{channel_username}: {e}")
                continue
    
    logger.info(f"✅ Найдено новых проектов: {len(new_projects)}")
    return new_projects

# ================== ИНИЦИАЛИЗАЦИЯ БОТА И ШЕДУЛЕРА ==================
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job('interval', minutes=CHECK_INTERVAL_MIN)
async def scheduled_check():
    """Запланированная проверка каналов"""
    try:
        results = await check_channels()
        if not results:
            logger.info("📭 Новых проектов не найдено")
            return
        
        # Отправка уведомлений
        for i, msg in enumerate(results, 1):
            try:
                await bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=msg,
                    disable_web_page_preview=False,
                    disable_notification=False
                )
                logger.info(f"📤 Отправлено уведомление {i}/{len(results)}")
                await asyncio.sleep(1)  # Задержка между сообщениями
            except Exception as e:
                logger.error(f"❌ Ошибка отправки: {e}")
        
        logger.info(f"✅ Все уведомления отправлены ({len(results)})")
    
    except Exception as e:
        logger.error(f"❌ Критическая ошибка при проверке: {e}")

# ================== КОМАНДЫ БОТА ==================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "✅ Парсер TG-каналов запущен!\n\n"
        f"Ключевые слова: {', '.join(KEYWORDS[:6])}...\n"
        f"Проверка каждые {CHECK_INTERVAL_MIN} мин\n"
        f"Мониторинг {len(CHANNELS)} каналов"
    )

@dp.message(Command("status"))
async def cmd_status(message: Message):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT COUNT(*) FROM sent") as cursor:
            total = (await cursor.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM sent WHERE timestamp > datetime('now', '-24 hours')"
        ) as cursor:
            last_24h = (await cursor.fetchone())[0]
    
    await message.answer(
        f"📊 Статистика:\n"
        f"• Всего найдено: {total}\n"
        f"• За последние 24ч: {last_24h}\n"
        f"• Интервал проверки: {CHECK_INTERVAL_MIN} мин"
    )

@dp.message(Command("check"))
async def cmd_check(message: Message):
    await message.answer("🔍 Запускаю ручную проверку каналов...")
    results = await check_channels()
    if results:
        await message.answer(f"✅ Найдено {len(results)} новых проектов")
        for msg in results[:3]:  # Отправляем максимум 3 в ответ
            await message.answer(msg, disable_web_page_preview=False)
        if len(results) > 3:
            await message.answer(f"📬 И ещё {len(results) - 3} проектов отправлено в ваш чат")
    else:
        await message.answer("📭 Новых проектов не найдено")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК ПАРСЕРА TG-КАНАЛОВ")
    logger.info("=" * 50)
    
    # Инициализация БД
    await init_db()
    
    # Авторизация в Telegram
    await client.start(phone=PHONE)
    await authorize(client)
    
    # Отправка стартового уведомления
    try:
        await bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text="✅ Парсер TG-каналов запущен на Railway!\n\n"
                 f"🔍 Мониторинг {len(CHANNELS)} каналов\n"
                 f"⏱️ Проверка каждые {CHECK_INTERVAL_MIN} минут\n"
                 f"🕒 Запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info("✅ Стартовое уведомление отправлено")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить стартовое уведомление: {e}")
    
    # Запуск шедулера
    scheduler.start()
    logger.info(f"⏰ Шедулер запущен (интервал: {CHECK_INTERVAL_MIN} мин)")
    
    # Запуск бота
    logger.info("🤖 Aiogram бот запущен. Ожидаю команды...")
    await dp.start_polling(bot, skip_updates=True)

# ================== ТОЧКА ВХОДА ==================
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Парсер остановлен пользователем")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
        raise
