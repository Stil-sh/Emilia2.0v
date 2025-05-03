import logging
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from asyncpg import create_pool
import aiohttp
from config import BOT_TOKEN, DB_CONFIG

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
        self.storage = MemoryStorage()
        self.dp = Dispatcher(self.bot, storage=self.storage)
        self.pool = None
        self.http_session = None
        self.cache = {}  # Простой in-memory кэш вместо Redis

    async def init_db(self):
        self.pool = await create_pool(**DB_CONFIG)
        async with self.pool.acquire() as conn:
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

    async def get_user(self, user_id: int):
        # Проверяем кэш перед запросом к БД
        if user_id in self.cache.get('users', {}):
            return self.cache['users'][user_id]
        
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT * FROM users WHERE user_id = $1", user_id
            )
            if user:
                if 'users' not in self.cache:
                    self.cache['users'] = {}
                self.cache['users'][user_id] = user
            return user

    async def get_waifu_image(self, genre: str, nsfw: bool = False):
        cache_key = f"image_{genre}_{nsfw}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            category = 'nsfw' if nsfw else 'sfw'
            async with self.http_session.get(
                f"https://api.waifu.pics/{category}/{genre}",
                timeout=3
            ) as resp:
                data = await resp.json()
                self.cache[cache_key] = data['url']  # Кэшируем результат
                return data['url']
        except Exception as e:
            logger.error(f"API Error: {e}")
            return None

    async def main_menu(self, user_id: int):
        keyboard = InlineKeyboardMarkup(row_width=2)
        genres = ["waifu", "neko", "shinobu", "megumin"]
        
        for genre in genres:
            keyboard.insert(InlineKeyboardButton(
                genre.capitalize(),
                callback_data=f"genre_{genre}"
            ))
        
        user = await self.get_user(user_id)
        if user:
            nsrw_text = "🔞 Выключить NSFW" if user['nsfw_enabled'] else "🔞 Включить NSFW"
            keyboard.row(InlineKeyboardButton(nsrw_text, callback_data="toggle_nsfw"))
        
        keyboard.row(
            InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
            InlineKeyboardButton("📊 Статистика", callback_data="stats")
        )
        
        return keyboard

    async def on_startup(self, dp):
        self.http_session = aiohttp.ClientSession()
        await self.init_db()
        logger.info("Бот успешно запущен")

    async def on_shutdown(self, dp):
        await self.http_session.close()
        await self.pool.close()
        logger.info("Бот остановлен")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start'])
        async def cmd_start(message: types.Message):
            user = await self.get_user(message.from_user.id)
            if not user:
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "INSERT INTO users (user_id, username) VALUES ($1, $2)",
                        message.from_user.id, message.from_user.username
                    )
            
            await message.answer(
                f"👋 Добро пожаловать, {message.from_user.first_name}!\n"
                "Выберите жанр:",
                reply_markup=await self.main_menu(message.from_user.id)
            )

        @self.dp.callback_query_handler(lambda c: c.data.startswith('genre_'))
        async def process_genre(call: types.CallbackQuery):
            user = await self.get_user(call.from_user.id)
            genre = call.data.split('_')[1]
            
            image_url = await self.get_waifu_image(
                genre, 
                user.get('nsfw_enabled', False) if user else False
            )
            
            if image_url:
                kb = InlineKeyboardMarkup()
                kb.add(InlineKeyboardButton(
                    "⭐ В избранное", 
                    callback_data=f"fav_{image_url}"
                ))
                
                await self.bot.send_photo(
                    call.from_user.id,
                    image_url,
                    reply_markup=kb
                )
            else:
                await call.answer("⚠️ Ошибка загрузки", show_alert=True)

        @self.dp.callback_query_handler(lambda c: c.data == 'toggle_nsfw')
        async def toggle_nsfw(call: types.CallbackQuery):
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE users SET nsfw_enabled = NOT nsfw_enabled WHERE user_id = $1",
                    call.from_user.id
                )
                # Очищаем кэш пользователя
                if 'users' in self.cache and call.from_user.id in self.cache['users']:
                    del self.cache['users'][call.from_user.id]
            
            await call.message.edit_reply_markup(
                reply_markup=await self.main_menu(call.from_user.id)
            )
            await call.answer("Настройки NSFW обновлены")

    def run(self):
        self.register_handlers()
        executor.start_polling(
            self.dp,
            on_startup=self.on_startup,
            on_shutdown=self.on_shutdown,
            skip_updates=True
        )

if __name__ == '__main__':
    bot = AnimeBot()
    bot.run()
