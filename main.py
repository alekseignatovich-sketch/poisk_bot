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
NOTIFY_CHAT_ID = int(os.getenv('YOUR_CHAT_ID', '0'))  # Куда слать проекты (ваш канал/группа)
API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH')
PHONE = os.getenv('PHONE')

# OWNER_ID — ваш личный Telegram ID (для команд)
# Если не задан — разрешаем команды из любого чата (временно для отладки)
OWNER_ID = int(os.getenv('OWNER_ID', '0'))

if not all([TOKEN, NOTIFY_CHAT_ID, API_ID, API_HASH, PHONE]):
    missing = [k for k, v in {
        'BOT_TOKEN': TOKEN,
        'YOUR_CHAT_ID': NOTIFY_CHAT_ID if NOTIFY_CHAT_ID else None,
        'API_ID': API_ID if API_ID else None,
        'API_HASH': API_HASH,
        'PHONE': PHONE
    }.items() if not v]
    raise RuntimeError(f"❌ Отсутствуют переменные: {', '.join(missing)}")

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
    async with aiosqlite.connect('projects.db') as db:
        await db.execute('CREATE TABLE IF NOT EXISTS sent (message_id TEXT PRIMARY KEY, channel TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)')
        await db.commit()
    logger.info("✅ База данных инициализирована")

# ================== КОМАНДЫ БОТА ==================
@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    # Логируем для отладки
    logger.info(f"💬 /start от chat.id={message.chat.id}, user.id={message.from_user.id}")
    
    # Проверка владельца (временно отключена для отладки — закомментируйте после настройки)
    # if OWNER_ID and message.from_user.id != OWNER_ID:
    #     await message.answer("🚫 Доступ запрещён")
    #     return
    
    global is_authorized
    
    if is_authorized:
        await message.answer(
            "✅ Парсер уже запущен!\n\n"
            "🔍 Мониторинг каналов на заказы по Python/Telegram\n"
            "⏱️ Проверка каждые 15 минут"
        )
        return
    
    if await client.is_user_authorized():
        is_authorized = True
        await message.answer("✅ Авторизация восстановлена из сессии — парсер активен!")
        logger.info("✅ Авторизация восстановлена")
        return
    
    # Запрашиваем код
    try:
        await client.send_code_request(PHONE)
        await state.set_state(AuthStates.waiting_for_code)
        await message.answer(
            "🔑 Код подтверждения отправлен в Telegram!\n\n"
            "1. Откройте официальное приложение Telegram\n"
            "2. Найдите сообщение от «Telegram» с 5-6 цифрами\n"
            "3. Отправьте код этому боту прямо здесь"
        )
        logger.info("📤 Запрошен код авторизации")
    except FloodWaitError as e:
        await message.answer(f"⏳ Telegram требует паузу {e.seconds} секунд. Попробуйте /start позже.")
        logger.warning(f"⏳ FloodWait: {e.seconds} сек")
    except Exception as e:
        logger.error(f"❌ Ошибка запроса кода: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:150]}")

@dp.message(AuthStates.waiting_for_code)
async def handle_code(message: Message, state: FSMContext):
    # if OWNER_ID and message.from_user.id != OWNER_ID:
    #     return
    
    code = ''.join(filter(str.isdigit, message.text))
    if len(code) not in (5, 6):
        await message.answer("❌ Неверный формат. Отправьте 5-6 цифр кода:")
        return
    
    try:
        await client.sign_in(PHONE, code)
        global is_authorized
        is_authorized = True
        await state.clear()
        
        await message.answer("✅ Авторизация успешна!")
        logger.info("✅ Авторизация завершена")
        
        # Отправляем стартовое уведомление В КАНАЛ/ГРУППУ (NOTIFY_CHAT_ID)
        await bot.send_message(
            chat_id=NOTIFY_CHAT_ID,
            text=(
                "🚀 Парсер TG-каналов запущен!\n\n"
                "🔍 Мониторинг заказов по Python/Telegram\n"
                f"⏱️ Первый поиск через 15 минут\n"
                f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
        )
        logger.info(f"✅ Стартовое уведомление отправлено в чат {NOTIFY_CHAT_ID}")
        
    except SessionPasswordNeededError:
        await state.set_state(AuthStates.waiting_for_password)
        await message.answer("🔐 Требуется пароль двухфакторной аутентификации:")
    except PhoneCodeInvalidError:
        await message.answer("❌ Неверный код. Попробуйте ещё раз:")
    except FloodWaitError as e:
        await message.answer(f"⏳ Слишком много попыток. Подождите {e.seconds} секунд.")
    except Exception as e:
        logger.error(f"❌ Ошибка авторизации: {e}")
        await message.answer(f"❌ Ошибка: {str(e)[:150]}")

@dp.message(AuthStates.waiting_for_password)
async def handle_password(message: Message, state: FSMContext):
    # if OWNER_ID and message.from_user.id != OWNER_ID:
    #     return
    
    try:
        await client.sign_in(password=message.text.strip())
        global is_authorized
        is_authorized = True
        await state.clear()
        await message.answer("✅ Авторизация с 2FA успешна!")
        logger.info("✅ Авторизация с паролем завершена")
        
        # Стартовое уведомление в канал
        await bot.send_message(NOTIFY_CHAT_ID, "✅ Парсер активен после 2FA!")
        
    except Exception as e:
        await message.answer(f"❌ Неверный пароль. Попробуйте ещё раз:")

# ================== ГЛАВНАЯ ФУНКЦИЯ ==================
async def main():
    logger.info("=" * 50)
    logger.info("🚀 ЗАПУСК ПАРСЕРА TG-КАНАЛОВ")
    logger.info("=" * 50)
    
    await init_db()
    await client.connect()
    logger.info("🔌 Подключено к Telegram")
    
    global is_authorized
    is_authorized = await client.is_user_authorized()
    
    if is_authorized:
        logger.info("✅ Авторизация восстановлена из сессии")
        try:
            await bot.send_message(
                chat_id=NOTIFY_CHAT_ID,
                text="✅ Парсер возобновил работу после перезапуска!"
            )
        except Exception as e:
            logger.warning(f"⚠️ Не удалось отправить уведомление в чат {NOTIFY_CHAT_ID}: {e}")
    else:
        logger.info("⚠️ Требуется авторизация — отправьте /start в личные сообщения боту")
    
    logger.info("🤖 Бот ожидает команды /start")
    await dp.start_polling(bot, skip_updates=True)

# ================== ТОЧКА ВХОДА ==================
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Остановлен пользователем")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
