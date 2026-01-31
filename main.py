import os
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command, Text
from aiogram.types import Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram import F

# ================== ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ==================
TOKEN = os.getenv('BOT_TOKEN')
YOUR_CHAT_ID = int(os.getenv('YOUR_CHAT_ID', '0'))
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')

if not all([TOKEN, YOUR_CHAT_ID, API_ID, API_HASH, PHONE]):
    missing = [k for k, v in {
        'BOT_TOKEN': TOKEN,
        'YOUR_CHAT_ID': YOUR_CHAT_ID if YOUR_CHAT_ID else None,
        'API_ID': API_ID if API_ID else None,
        'API_HASH': API_HASH,
        'PHONE': PHONE
    }.items() if not v]
    raise RuntimeError(f"❌ Отсутствуют переменные: {', '.join(missing)}")

# ================== НАСТРОЙКИ ==================
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

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ================== FSM ДЛЯ АВТОРИЗАЦИИ ==================
class AuthStates(StatesGroup):
    waiting_for_code = State()
    waiting_for_password = State()

# ================== ИНИЦИАЛИЗАЦИЯ ==================
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
client = TelegramClient('railway_session', API_ID, API_HASH)
scheduler = AsyncIOScheduler()
auth_lock = asyncio.Lock()
is_authorized = False

# ================== БАЗА ДАННЫХ ==================
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

# ================== АВТОРИЗАЦИЯ ЧЕРЕЗ БОТА ==================
async def request_code():
    """Запрос кода через официальный клиент Telegram"""
    global is_authorized
    
    async with auth_lock:
        if await client.is_user_authorized():
            is_authorized = True
            logger.info("✅ Уже авторизован")
            return True
        
        try:
            await client.send_code_request(PHONE)
            logger.info("📤 Код отправлен в Telegram")
            await bot.send_message(
                chat_id=YOUR_CHAT_ID,
                text=(
                    "🔑 Требуется авторизация в Telegram!\n\n"
                    "1. Откройте официальное приложение Telegram\n"
                    "2. Найдите сообщение от «Telegram» с кодом (6 цифр)\n"
                    "3. Отправьте код этому боту прямо здесь\n\n"
                    "⚠️ Код действителен 2 минуты"
                )
            )
            return False
        except Exception as e:
            logger.error(f"❌ Ошибка запроса кода: {e}")
            await bot.send_message(
                chat_id=YOUR_CHAT_ID,
                text=f"❌ Ошибка запроса кода: {e}\n\nПопробуйте перезапустить приложение (/start)"
            )
            return False

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.chat.id != YOUR_CHAT_ID:
        await message.answer("🚫 Доступ запрещён")
        return
    
    await state.clear()
    await message.answer(
        "✅ Парсер TG-каналов запущен!\n\n"
        f"🔍 Мониторинг {len(CHANNELS)} каналов\n"
        f"⏱️ Проверка каждые {CHECK_INTERVAL_MIN} мин\n\n"
        "Если требуется авторизация — я попрошу код здесь."
    )
    
    # Запуск авторизации при старте
    global is_authorized
    if not is_authorized:
        await request_code()

@dp.message(AuthStates.waiting_for_code)
async def handle_code(message: Message, state: FSMContext):
    if message.chat.id != YOUR_CHAT_ID:
        return
    
    code = message.text.strip()
    if not code.isdigit() or len(code) != 5 and len(code) != 6:
        await message.answer("❌ Неверный формат кода. Отправьте 5-6 цифр:")
        return
    
    try:
        await client.sign_in(PHONE, code)
        global is_authorized
        is_authorized = True
        await state.clear()
        
        await message.answer("✅ Авторизация успешна!")
        logger.info("✅ Авторизация через код завершена")
        
        # Отправка стартового уведомления
        await bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text=(
                "🚀 Парсер полностью запущен!\n\n"
                f"🔍 Мониторинг {len(CHANNELS)} каналов\n"
                f"⏱️ Первый поиск через {CHECK_INTERVAL_MIN} мин\n"
                f"🕒 Запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        
        # Запуск шедулера (если ещё не запущен)
        if not scheduler.running:
            scheduler.start()
            logger.info(f"⏰ Шедулер запущен (интервал: {CHECK_INTERVAL_MIN} мин)")
            
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
    except SessionPasswordNeededError:
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer("🔐 Требуется пароль двухфакторной аутентификации. Отправьте пароль:")
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте /start")

@dp.message(AuthStates.waiting_for_password)
async def handle_password(message: Message, state: FSMContext):
    if message.chat.id != YOUR_CHAT_ID:
        return
    
    try:
        await client.sign_in(password=message.text.strip())
        global is_authorized
        is_authorized = True
        await state.clear()
        
        await message.answer("✅ Авторизация с 2FA успешна!")
        logger.info("✅ Авторизация с паролем завершена")
        
        # Стартовое уведомление
        await bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text=(
                "🚀 Парсер полностью запущен!\n\n"
                f"🔍 Мониторинг {len(CHANNELS)} каналов\n"
                f"⏱️ Первый поиск через {CHECK_INTERVAL_MIN} мин"
            )
        )
        
        if not scheduler.running:
            scheduler.start()
            logger.info(f"⏰ Шедулер запущен (интервал: {CHECK_INTERVAL_MIN} мин)")
            
    except Exception as e:
        logger.error(f"❌ Ошибка 2FA: {e}")
        await message.answer(f"❌ Неверный пароль: {e}\n\nПопробуйте ещё раз:")

# ================== ПАРСИНГ КАНАЛОВ ==================
async def check_channels():
    if not is_authorized:
        logger.warning("⚠️ Пропуск проверки — не авторизован")
        return []
    
    logger.info(f"🔍 Проверка {len(CHANNELS)} каналов...")
    new_projects = []
    
    async with aiosqlite.connect(DB_FILE) as db:
        for channel_username in CHANNELS:
            try:
                entity = await client.get_entity(channel_username)
                messages = await client.get_messages(entity, limit=5)
                
                for msg in messages:
                    if not msg.text:
                        continue
                    
                    text_lower = msg.text.lower()
                    msg_id = f"{channel_username}_{msg.id}"
                    
                    if any(kw.lower() in text_lower for kw in KEYWORDS):
                        async with db.execute("SELECT 1 FROM sent WHERE message_id=?", (msg_id,)) as cursor:
                            if await cursor.fetchone() is None:
                                await db.execute(
                                    "INSERT INTO sent (message_id, channel) VALUES (?, ?)",
                                    (msg_id, channel_username)
                                )
                                await db.commit()
                                
                                link = f"https://t.me/{channel_username}/{msg.id}"  # ✅ Без пробелов!
                                preview = msg.text[:250] + "..." if len(msg.text) > 250 else msg.text
                                
                                message = (
                                    f"🆕 Новый проект в @{channel_username}\n\n"
                                    f"{preview}\n\n"
                                    f"🔗 {link}"
                                )
                                new_projects.append(message)
                
                await asyncio.sleep(3)
                
            except Exception as e:
                logger.warning(f"⚠️ Ошибка @{channel_username}: {e}")
                continue
    
    logger.info(f"✅ Найдено новых проектов: {len(new_projects)}")
    return new_projects

@scheduler.scheduled_job('interval', minutes=CHECK_INTERVAL_MIN)
async def scheduled_check():
    try:
        results = await check_channels()
        if not results:
            logger.info("📭 Новых проектов не найдено")
            return
        
        for i, msg in enumerate(results, 1):
            try:
                await bot.send_message(
                    chat_id=YOUR_CHAT_ID,
                    text=msg,
                    disable_web_page_preview=False
                )
                logger.info(f"📤 Отправлено {i}/{len(results)}")
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка отправки: {e}")
    
    except Exception as e:
        logger.error(f"❌ Ошибка проверки: {e}")

# ================== КОМАНДЫ ==================
@dp.message(Command("status"))
async def cmd_status(message: Message):
    if message.chat.id != YOUR_CHAT_ID:
        return
    
    status = "✅ Авторизован" if is_authorized else "⚠️ Ожидает авторизацию"
    await message.answer(
        f"📊 Статус:\n• Авторизация: {status}\n• Шедулер: {'Запущен' if scheduler.running else 'Остановлен'}"
    )

@dp.message(Command("check"))
async def cmd_check(message: Message):
    if message.chat.id != YOUR_CHAT_ID:
        return
    
    if not is_authorized:
        await message.answer("⚠️ Сначала завершите авторизацию!")
        return
    
    await message.answer("🔍 Запускаю ручную проверку...")
    results = await check_channels()
    
    if results:
        await message.answer(f"✅ Найдено {len(results)} проектов")
        for msg in results[:3]:
            await message.answer(msg, disable_web_page_preview=False)
        if len(results) > 3:
            await message.answer(f"📬 И ещё {len(results) - 3} проектов отправлено в чат")
    else:
        await message.answer("📭 Новых проектов не найдено")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК ПАРСЕРА TG-КАНАЛОВ (Railway Edition)")
    logger.info("=" * 50)
    
    await init_db()
    
    # Подключаемся к Telegram (без авторизации)
    await client.connect()
    logger.info("🔌 Подключено к Telegram")
    
    # Проверяем авторизацию
    global is_authorized
    is_authorized = await client.is_user_authorized()
    
    if is_authorized:
        logger.info("✅ Уже авторизован — запускаем шедулер")
        scheduler.start()
        await bot.send_message(
            chat_id=YOUR_CHAT_ID,
            text=(
                "✅ Парсер запущен!\n\n"
                f"🔍 Мониторинг {len(CHANNELS)} каналов\n"
                f"⏱️ Проверка каждые {CHECK_INTERVAL_MIN} мин\n"
                f"🕒 Возобновлен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
    else:
        logger.info("⚠️ Требуется авторизация — ожидаем код в чате")
    
    # Запуск бота
    logger.info("🤖 Aiogram бот запущен. Ожидаю команды...")
    await dp.start_polling(bot, skip_updates=True)

# ================== ТОЧКА ВХОДА ==================
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановлен пользователем")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
        raise
