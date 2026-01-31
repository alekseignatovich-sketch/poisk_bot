import os
import asyncio
import logging
from datetime import datetime
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, FloodWaitError
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

# ================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==================
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
KEYWORDS = ['telegram', 'бот', 'python', 'aiogram', 'parser', 'чат-бот', 'разработка', 'скрипт', 'автоматизация', 'freelance', 'заказ', 'проект']
CHANNELS = ['freelansim_ru', 'TGwork', 'partnerkin_job', 'work_on', 'FreeVacanciesIT', 'ru_pythonjobs', 'python_job', 'programming_orders']
DB_FILE = 'projects.db'
CHECK_INTERVAL_MIN = 15

# ================== ЛОГИРОВАНИЕ ==================
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)-8s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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
is_authorized = False

# ================== БАЗА ДАННЫХ ==================
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (message_id TEXT PRIMARY KEY, channel TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        await db.commit()
    logger.info("✅ База данных инициализирована")

# ================== АВТОРИЗАЦИЯ ==================
async def safe_send_code():
    try:
        await client.send_code_request(PHONE)
        return True, None
    except FloodWaitError as e:
        wait_time = e.seconds
        logger.warning(f"⏳ FloodWait: подождите {wait_time} секунд")
        return False, wait_time
    except Exception as e:
        logger.error(f"❌ Ошибка запроса кода: {e}")
        return False, None

# ================== КОМАНДЫ БОТА ==================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    if message.chat.id != YOUR_CHAT_ID:
        await message.answer("🚫 Доступ запрещён")
        return
    
    await state.clear()
    global is_authorized
    
    if is_authorized:
        await message.answer(f"✅ Парсер уже запущен!\n🔍 Мониторинг {len(CHANNELS)} каналов\n⏱️ Проверка каждые {CHECK_INTERVAL_MIN} мин")
        return
    
    if await client.is_user_authorized():
        is_authorized = True
        await message.answer("✅ Уже авторизован — парсер активен!")
        logger.info("✅ Авторизация восстановлена из сессии")
        return
    
    success, wait_time = await safe_send_code()
    if not success:
        if wait_time:
            await message.answer(f"⏳ Подождите {wait_time} секунд перед повторной попыткой.\nПопробуйте /start через {wait_time // 60 + 1} минут.")
        else:
            await message.answer("❌ Не удалось запросить код. Проверьте номер телефона.")
        return
    
    await state.set_state(AuthStates.waiting_for_code)
    await message.answer(
        "🔑 Код подтверждения отправлен в Telegram!\n\n"
        "1. Откройте официальное приложение Telegram\n"
        "2. Найдите сообщение от «Telegram» с 5-6 цифрами\n"
        "3. Отправьте код этому боту прямо здесь\n\n"
        "⚠️ Код действителен 2 минуты"
    )

@dp.message(AuthStates.waiting_for_code)
async def handle_code(message: Message, state: FSMContext):
    if message.chat.id != YOUR_CHAT_ID:
        return
    
    code = message.text.replace(' ', '').replace('-', '').strip()
    if not code.isdigit() or len(code) not in (5, 6):
        await message.answer("❌ Неверный формат. Отправьте 5-6 цифр кода:")
        return
    
    try:
        await client.sign_in(PHONE, code)
        global is_authorized
        is_authorized = True
        await state.clear()
        await message.answer("✅ Авторизация успешна! Парсер запущен.")
        logger.info("✅ Авторизация завершена")
        await bot.send_message(YOUR_CHAT_ID, f"🚀 Парсер активен!\n🔍 {len(CHANNELS)} каналов\n⏱️ Проверка каждые {CHECK_INTERVAL_MIN} мин")
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
    except SessionPasswordNeededError:
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer("🔐 Требуется пароль 2FA:")
    except FloodWaitError as e:
        await message.answer(f"⏳ Подождите {e.seconds} секунд и попробуйте /start")
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:200]}")

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
    except Exception as e:
        await message.answer(f"❌ Неверный пароль. Попробуйте ещё раз:")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК ПАРСЕРА (Railway Edition)")
    logger.info("=" * 50)
    
    await init_db()
    await client.connect()
    logger.info("🔌 Подключено к Telegram")
    
    global is_authorized
    is_authorized = await client.is_user_authorized()
    
    if is_authorized:
        logger.info("✅ Авторизация восстановлена из сессии")
        await bot.send_message(YOUR_CHAT_ID, "✅ Парсер возобновил работу после перезапуска!")
    else:
        logger.info("⚠️ Требуется авторизация — отправьте /start")
        await bot.send_message(YOUR_CHAT_ID, "👋 Отправьте /start для авторизации в Telegram")
    
    logger.info("🤖 Бот ожидает команду /start")
    await dp.start_polling(bot, skip_updates=True)

# ================== ТОЧКА ВХОДА ==================
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановлен пользователем")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
