import os
import asyncio
import base64
import logging
from datetime import datetime
from telethon import TelegramClient
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# ================== ВОССТАНОВЛЕНИЕ СЕССИИ ==================
session_part1 = os.getenv('SESSION_PART1', '')
session_part2 = os.getenv('SESSION_PART2', '')

if session_part1:
    try:
        full_base64 = session_part1 + session_part2
        session_data = base64.b64decode(full_base64)
        with open('railway_session.session', 'wb') as f:
            f.write(session_data)
        print(f"✅ Сессия восстановлена ({len(session_data)} байт)")
    except Exception as e:
        print(f"❌ Ошибка восстановления: {e}")
        exit(1)

# ================== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==================
TOKEN = os.getenv('BOT_TOKEN')
NOTIFY_CHAT_ID = int(os.getenv('YOUR_CHAT_ID'))
API_ID = int(os.getenv('API_ID', '30822050'))
API_HASH = os.getenv('API_HASH', '656e7cb50ff9753230d609d0e2a6b701')

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher()
client = TelegramClient('railway_session', API_ID, API_HASH)

# ================== РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА ==================
KEYWORDS = [
    # Основные технологии
    'telegram', 'телеграм', 'бот', 'бота', 'боты', 'chatbot', 'чат-бот', 'мессенджер',
    'python', 'питон', 'пайтон', 'django', 'flask', 'fastapi', 'aiohttp', 'aiogram',
    'aiogram3', 'aiogram2', 'pyrogram', 'telethon', 'telebot', 'python-telegram-bot',
    
    # Типы проектов
    'парсер', 'парсинг', 'скрапинг', 'crawler', 'scraper', 'сбор данных', 'парсить',
    'автоматизация', 'автоматизировать', 'скрипт', 'скрипты', 'автоскрипт',
    'интеграция', 'апи', 'api', 'webhook', 'вебхук', 'rest api', 'json',
    
    # Разработка и заказы
    'разработка', 'разработать', 'написать', 'сделать', 'создать', 'заказ', 'проект',
    'задача', 'тз', 'техническое задание', 'требуется', 'ищу', 'нужен', 'нужна',
    'разработчик', 'программист', 'кодер', 'coder', 'developer',
    
    # Фриланс и работа
    'фриланс', 'freelance', 'удалёнка', 'удаленка', 'удалённо', 'удаленно', 'remote',
    'работа', 'вакансия', 'job', 'hire', 'нанять', 'исполнитель', 'подряд',
    
    # Бизнес и услуги
    'бизнес', 'магазин', 'shop', 'интернет-магазин', 'продажи', 'продажа', 'продаж',
    'заказы', 'приём заказов', 'прием заказов', 'бронирование', 'запись', 'услуги',
    'клиенты', 'crm', 'база данных', 'database', 'sql', 'postgresql', 'mysql',
    
    # Монетизация и платежи
    'платежи', 'payment', 'оплата', 'киви', 'qiwi', 'yoomoney', 'юмани', 'stripe',
    'крипта', 'криптовалюта', 'биткоин', 'bitcoin', 'usdt', 'ton', 'кошелёк',
    
    # Дополнительные технологии
    'база данных', 'бд', 'database', 'sqlite', 'postgresql', 'mysql', 'mongodb',
    'docker', 'докер', 'сервер', 'хостинг', 'vps', 'vds', 'linux', 'ubuntu',
    'javascript', 'node.js', 'react', 'vue', 'фронтенд', 'frontend', 'backend',
    'селениум', 'selenium', 'selenium', 'браузер', 'автоматизация браузера',
    
    # Сроки и бюджет
    'срочно', 'срочно нужен', 'срочно требуется', 'быстро', 'на сейчас',
    'бюджет', 'стоимость', 'цена', 'прайс', 'rate', 'стоимость', 'деньги',
    'дедлайн', 'deadline', 'срок', 'неделя', 'день', 'час', 'срочно',
    
    # Дополнительные слова для охвата
    'помощь', 'помогите', 'помогу', 'консультация', 'совет', 'совет нужен',
    'пример', 'пример кода', 'код', 'исходник', 'source code', 'github',
    'ошибка', 'баг', 'исправить', 'починить', 'доделать', 'доработать',
    'продолжить', 'закончить', 'дописать', 'рефакторинг', 'оптимизация'
]

# ================== РАСШИРЕННЫЙ СПИСОК КАНАЛОВ ==================
CHANNELS = [
    # 🇷🇺 Фриланс-биржи и заказы
    'freelansim_ru', 'TGwork', 'partnerkin_job', 'work_on', 'FreeVacanciesIT',
    'webfrl', 'distantsiya', 'udalenka_chat', 'freelancehunt_ru', 'freelancejobs',
    'job_telegram', 'freelance_chat_ru', 'freelance_ru', 'freelance_birzha',
    
    # 🐍 Python-разработка и вакансии
    'ru_pythonjobs', 'python_job', 'python_vacancies', 'python_vacancy',
    'pythonjobs', 'pythondev', 'python_developers', 'python_programmers',
    'django_ru', 'flask_ru', 'fastapi_ru', 'aiohttp_ru',
    
    # 🤖 Telegram-разработка и боты
    'tgram_jobs', 'tgdev_jobs', 'telegram_dev', 'telegram_developers',
    'telegram_bots', 'telegram_bot_dev', 'telegram_api_ru', 'tg_api_dev',
    'aiogram_ru', 'aiogram_chat', 'pyrogram_ru', 'telethon_ru',
    
    # 💼 IT-вакансии и карьера
    'habr_career', 'get_it_jobs', 'it_vacancies', 'it_jobs_ru', 'it_job',
    'pro_jvm_jobs', 'data_science_jobs', 'backend_jobs', 'frontend_jobs',
    'devops_jobs', 'qa_jobs', 'mobile_jobs', 'game_dev_jobs',
    
    # 🌐 Удалённая работа
    'remote_jobs_ru', 'remote_dev', 'remote_it', 'remote_work_ru', 'udalennaya_rabota',
    'digital_nomads', 'work_from_home', 'home_office_ru',
    
    # 📊 Программирование и заказы
    'programming_orders', 'code_orders', 'dev_orders', 'prog_jobs',
    'it_freelance', 'prog_freelance', 'dev_freelance', 'code_freelance',
    
    # 🎯 Ниша: боты и автоматизация
    'bot_development', 'bot_orders', 'automation_orders', 'parser_orders',
    'telegram_automation', 'tg_automation', 'auto_posting', 'auto_moderation',
    
    # 🏪 Бизнес и стартапы
    'startup_jobs', 'startup_hiring', 'business_it', 'it_business_ru',
    'digital_agency', 'web_studio', 'it_company', 'tech_startup',
    
    # 📱 Мобильная разработка
    'mobile_dev_jobs', 'android_jobs', 'ios_jobs', 'flutter_jobs',
    'kotlin_jobs', 'swift_jobs', 'react_native_jobs',
    
    # 🎨 Дизайн и фронтенд
    'frontend_jobs', 'web_design_jobs', 'ui_ux_jobs', 'figma_jobs',
    'react_jobs', 'vue_jobs', 'angular_jobs', 'html_css_jobs'
]

async def init_db():
    async with aiosqlite.connect('projects.db') as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sent (
                message_id TEXT PRIMARY KEY,
                channel TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON sent(timestamp)')
        await db.commit()

async def check_channels():
    new_projects = []
    async with aiosqlite.connect('projects.db') as db:
        for channel in CHANNELS:
            try:
                messages = await client.get_messages(channel, limit=5)
                for msg in messages:
                    if not msg.text: continue
                    
                    text_lower = msg.text.lower()
                    
                    # Проверяем ключевые слова
                    found_keywords = [kw for kw in KEYWORDS if kw.lower() in text_lower]
                    if not found_keywords:
                        continue
                    
                    msg_id = f"{channel}_{msg.id}"
                    
                    # Проверяем, не отправляли ли уже
                    async with db.execute("SELECT 1 FROM sent WHERE message_id=?", (msg_id,)) as cur:
                        if await cur.fetchone():
                            continue
                    
                    # Сохраняем в БД
                    await db.execute("INSERT INTO sent (message_id, channel) VALUES (?, ?)", (msg_id, channel))
                    await db.commit()
                    
                    # Формируем сообщение
                    link = f"https://t.me/{channel}/{msg.id}"
                    
                    # Обрезаем текст до 350 символов для лучшей читаемости
                    preview = msg.text[:350]
                    if len(msg.text) > 350:
                        preview += "..."
                    
                    # Подсвечиваем найденные ключевые слова
                    highlighted = preview
                    for kw in found_keywords[:3]:  # Подсвечиваем первые 3 ключевых слова
                        highlighted = highlighted.replace(kw, f"**{kw}**")
                    
                    message = (
                        f"🆕 Новый заказ в @{channel}\n\n"
                        f"{highlighted}\n\n"
                        f"🔗 {link}"
                    )
                    new_projects.append(message)
                
                await asyncio.sleep(2)  # Задержка между каналами
                
            except Exception as e:
                logger.debug(f"⏭️ Пропущен @{channel}: {str(e)[:60]}")
                continue
    
    return new_projects

@dp.message(Command("start"))
async def start(message: Message):
    stats_text = (
        "🤖 @MyyFreelance_Bot активен!\n\n"
        f"📊 Статистика мониторинга:\n"
        f"• Каналов: {len(CHANNELS)}\n"
        f"• Ключевых слов: {len(KEYWORDS)}\n"
        f"• Автопроверка: каждые 15 минут\n\n"
        "⚡ Команды:\n"
        "/check - Ручная проверка каналов на заказы\n"
        "/stats - Статистика найденных заказов"
    )
    await message.answer(stats_text)

@dp.message(Command("check"))
async def check(message: Message):
    await message.answer("🔍 Запуск проверки всех каналов...")
    results = await check_channels()
    
    if results:
        await message.answer(f"✅ Найдено {len(results)} новых заказов!")
        
        # Отправляем первые 5 заказов в ответ
        for i, msg in enumerate(results[:5], 1):
            await message.answer(
                f"📝 Заказ #{i}:\n{msg}",
                disable_web_page_preview=False
            )
            await asyncio.sleep(0.5)
        
        # Если нашли больше 5, сообщаем
        if len(results) > 5:
            await message.answer(f"📬 И ещё {len(results) - 5} заказов отправлено в основной чат")
        
        # Отправляем все заказы в основной чат
        for msg in results:
            try:
                await bot.send_message(
                    chat_id=NOTIFY_CHAT_ID,
                    text=msg,
                    disable_web_page_preview=False
                )
                await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"❌ Ошибка отправки в основной чат: {e}")
    else:
        await message.answer("📭 Новых заказов не найдено. Проверка будет автоматически через 15 минут.")

@dp.message(Command("stats"))
async def stats(message: Message):
    async with aiosqlite.connect('projects.db') as db:
        # Всего найдено
        async with db.execute("SELECT COUNT(*) FROM sent") as cur:
            total = (await cur.fetchone())[0]
        
        # За последние 24 часа
        async with db.execute(
            "SELECT COUNT(*) FROM sent WHERE timestamp > datetime('now', '-24 hours')"
        ) as cur:
            last_24h = (await cur.fetchone())[0]
        
        # Топ-5 каналов
        async with db.execute(
            "SELECT channel, COUNT(*) as cnt FROM sent GROUP BY channel ORDER BY cnt DESC LIMIT 5"
        ) as cur:
            top_channels = await cur.fetchall()
    
    top_channels_text = "\n".join([f"• @{ch}: {cnt} заказов" for ch, cnt in top_channels]) if top_channels else "Нет данных"
    
    stats_text = (
        "📊 Статистика бота:\n\n"
        f"📈 Всего найдено заказов: {total}\n"
        f"⏰ За последние 24 часа: {last_24h}\n"
        f"📡 Мониторинг каналов: {len(CHANNELS)}\n\n"
        f"🏆 Топ-5 каналов по заказам:\n{top_channels_text}"
    )
    await message.answer(stats_text)

async def main():
    logger.info("=" * 60)
    logger.info("🚀 @MyyFreelance_Bot ЗАПУЩЕН")
    logger.info(f"📡 Мониторинг {len(CHANNELS)} каналов")
    logger.info(f"🔑 {len(KEYWORDS)} ключевых слов")
    logger.info("=" * 60)
    
    await init_db()
    await client.connect()
    
    # Проверяем авторизацию
    is_auth = await client.is_user_authorized()
    logger.info(f"✅ Авторизован: {is_auth}")
    
    if not is_auth:
        logger.error("❌ Сессия недействительна! Требуется повторная авторизация.")
        return
    
    # Отправка стартового уведомления
    try:
        await bot.send_message(
            NOTIFY_CHAT_ID,
            "✅ @MyyFreelance_Bot активен!\n\n"
            f"📡 Мониторинг {len(CHANNELS)} каналов на заказы\n"
            f"🔑 {len(KEYWORDS)} ключевых слов для поиска\n"
            f"⏱️ Автопроверка каждые 15 минут\n"
            f"🕒 Запущен: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
            "💬 Отправьте /check для ручной проверки"
        )
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить стартовое уведомление: {e}")
    
    # Первая проверка
    logger.info("🔍 Запуск первой проверки каналов...")
    await check_channels()
    logger.info("✅ Первая проверка завершена")
    
    # Запуск бота
    logger.info("🤖 Aiogram бот запущен. Ожидаю команды...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
