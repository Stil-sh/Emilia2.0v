import logging
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.redis import RedisStorage2
from aiocache import cached, RedisCache
from asyncpg import create_pool
import aiohttp
from config import BOT_TOKEN, DB_CONFIG, REDIS_CONFIG

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
storage = RedisStorage2(**REDIS_CONFIG)
dp = Dispatcher(bot, storage=storage)

# Глобальные объекты
pool = None
http_session = None

# Класс для работы с БД
class Database:
    @staticmethod
    async def get_user(user_id: int):
        async with pool.acquire() as conn:
            return await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )

    @staticmethod
    async def add_to_favorites(user_id: int, image_url: str):
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO favorites (user_id, image_url) VALUES ($1, $2)",
                user_id, image_url
            )

# Кэшированные методы
class CachedMethods:
    @staticmethod
    @cached(ttl=300, cache=RedisCache, key_builder=lambda f, *args: f"user:{args[0]}")
    async def get_user_cached(user_id: int):
        return await Database.get_user(user_id)

    @staticmethod
    @cached(ttl=1800, cache=RedisCache)
    async def get_waifu_image(genre: str, nsfw: bool = False):
        try:
            category = 'nsfw' if nsfw else 'sfw'
            async with http_session.get(
                f"https://api.waifu.pics/{category}/{genre}",
                timeout=3
            ) as resp:
                data = await resp.json()
                return data['url']
        except Exception as e:
            logger.error(f"API Error: {e}")
            return None

# Генераторы клавиатур
class Keyboards:
    @staticmethod
    async def main_menu(user_id: int):
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Основные жанры
        genres = ["waifu", "neko", "shinobu", "megumin"]
        for genre in genres:
            keyboard.insert(InlineKeyboardButton(
                genre.capitalize(),
                callback_data=f"genre_{genre}"
            ))
        
        # Дополнительные кнопки
        user = await CachedMethods.get_user_cached(user_id)
        nsrw_btn = InlineKeyboardButton(
            "🔞 Выключить NSFW" if user.get('nsfw_enabled') else "🔞 Включить NSFW",
            callback_data="toggle_nsfw"
        )
        
        keyboard.row(nsrw_btn)
        keyboard.row(
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
            InlineKeyboardButton("📊 Статистика", callback_data="stats")
        )
        
        return keyboard

# Обработчики команд
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user = await CachedMethods.get_user_cached(message.from_user.id)
    if not user:
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                message.from_user.id, message.from_user.username
            )
    
    await message.answer(
        f"👋 Добро пожаловать, {message.from_user.first_name}!\n"
        "Выберите жанр:",
        reply_markup=await Keyboards.main_menu(message.from_user.id)
    )

@dp.callback_query_handler(lambda c: c.data.startswith('genre_'))
async def process_genre(call: types.CallbackQuery):
    user = await CachedMethods.get_user_cached(call.from_user.id)
    genre = call.data.split('_')[1]
    
    image_url = await CachedMethods.get_waifu_image(
        genre, 
        user.get('nsfw_enabled', False)
    )
    
    if image_url:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton(
            "⭐ В избранное", 
            callback_data=f"fav_{image_url}"
        ))
        
        await bot.send_photo(
            call.from_user.id,
            image_url,
            reply_markup=kb
        )
    else:
        await call.answer("⚠️ Ошибка загрузки", show_alert=True)

# Админ-команды
@dp.message_handler(commands=['admin'])
async def cmd_admin(message: types.Message):
    user = await CachedMethods.get_user_cached(message.from_user.id)
    if user.get('is_admin'):
        await message.answer(
            "⚙️ Админ-панель:",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("Статистика", callback_data="admin_stats"),
                InlineKeyboardButton("Рассылка", callback_data="admin_broadcast")
            )
        )

# Инициализация
async def on_startup(dp):
    global pool, http_session
    
    # Инициализация подключений
    pool = await create_pool(**DB_CONFIG)
    http_session = aiohttp.ClientSession()
    
    # Создание таблиц
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                nsfw_enabled BOOLEAN DEFAULT FALSE,
                is_admin BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                image_url TEXT,
                saved_at TIMESTAMP DEFAULT NOW()
            )
        """)
    
    logger.info("Бот успешно запущен")

async def on_shutdown(dp):
    await pool.close()
    await http_session.close()
    logger.info("Бот остановлен")

if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
    await http_session.close()
    logger.info("Бот остановлен")

if __name__ == '__main__':
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )
