import logging
import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import RetryAfter, NetworkError
from datetime import datetime
import sqlite3
from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID

# Настройка логов
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
conn = sqlite3.connect('bot_stats.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   username TEXT,
                   first_name TEXT,
                   last_name TEXT,
                   join_date TEXT,
                   is_premium INTEGER DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS stats
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   command TEXT,
                   timestamp TEXT)''')
conn.commit()

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN, parse_mode='HTML')
        self.storage = MemoryStorage()
        self.dp = Dispatcher(self.bot, storage=self.storage)
        
        # Категории
        self.sfw_genres = ["waifu", "neko", "shinobu", "megumin", "awoo", "smug", "bonk", "yeet", 
                          "blush", "wave", "highfive", "handhold", "nom", "bite", "glomp", "slap"]
        
        self.nsfw_genres = ["waifu", "neko", "trap", "blowjob", "cum", "les", "solo", "anal", 
                           "holo", "ero", "feet", "yuri", "thighs", "pussy", "futanari"]
        
        self.premium_genres = ["maid", "marin-kitagawa", "raiden-shogun", "oppai", "selfies", "uniform"]
        
        self.nsfw_enabled = False
        self.session = None
        self.channel_id = CHANNEL_ID
        self.admin_id = ADMIN_ID

    async def on_startup(self, dp):
        self.session = aiohttp.ClientSession()
        logger.info("Бот успешно запущен")
        await self.bot.send_message(self.admin_id, "🤖 Бот успешно запущен")

    async def on_shutdown(self, dp):
        await self.session.close()
        conn.close()
        logger.info("Бот остановлен")
        await self.bot.send_message(self.admin_id, "🤖 Бот остановлен")

    async def check_subscription(self, user_id):
        try:
            member = await self.bot.get_chat_member(self.channel_id, user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

    async def save_user(self, user: types.User):
        cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date) VALUES (?, ?, ?, ?, ?)",
                      (user.id, user.username, user.first_name, user.last_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    async def log_command(self, command):
        cursor.execute("INSERT INTO stats (command, timestamp) VALUES (?, ?)",
                      (command, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()

    async def get_stats(self):
        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM stats WHERE command='start'")
        total_starts = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_id) FROM stats WHERE date(timestamp) = date('now')")
        daily_active = cursor.fetchone()[0]
        
        return {
            "total_users": total_users,
            "total_starts": total_starts,
            "daily_active": daily_active
        }

    def get_main_menu(self, user_id=None):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        # Проверяем премиум статус
        is_premium = False
        if user_id:
            cursor.execute("SELECT is_premium FROM users WHERE user_id=?", (user_id,))
            result = cursor.fetchone()
            is_premium = result[0] if result else False
        
        # Показываем разные жанры в зависимости от режима
        genres_to_show = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
        if is_premium:
            genres_to_show += self.premium_genres
            
        for genre in genres_to_show:
            keyboard.add(KeyboardButton(genre.capitalize()))
            
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(KeyboardButton(nsfw_text))
        
        if not is_premium:
            keyboard.add(KeyboardButton("💎 Получить премиум"))
            
        keyboard.add(KeyboardButton("🔄 Обновить меню"), KeyboardButton("📊 Статистика"))
        return keyboard

    async def get_waifu_image(self, genre: str):
        try:
            category = 'nsfw' if self.nsfw_enabled else 'sfw'
            url = f"https://api.waifu.pics/{category}/{genre.lower()}"
            
            async with self.session.get(url, timeout=5) as response:
                if response.status != 200:
                    logger.error(f"API вернул статус {response.status}")
                    return None
                
                data = await response.json()
                return data['url']
                
        except asyncio.TimeoutError:
            logger.error("Таймаут запроса к API")
            return None
        except Exception as e:
            logger.error(f"Ошибка API: {str(e)}")
            return None

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            try:
                await self.save_user(message.from_user)
                await self.log_command('start')
                
                if not await self.check_subscription(message.from_user.id):
                    keyboard = InlineKeyboardMarkup()
                    keyboard.add(InlineKeyboardButton("Подписаться", url=f"https://t.me/{self.channel_id}"))
                    keyboard.add(InlineKeyboardButton("Я подписался", callback_data="check_sub"))
                    
                    await message.answer(
                        "📢 Для использования бота необходимо подписаться на наш канал!",
                        reply_markup=keyboard
                    )
                    return
                
                await message.answer(
                    "🎌 Добро пожаловать в Эмилию!\nВыберите жанр:",
                    reply_markup=self.get_main_menu(message.from_user.id)
                )
            except Exception as e:
                logger.error(f"Ошибка в /start: {str(e)}")

        @self.dp.callback_query_handler(lambda c: c.data == "check_sub")
        async def check_subscription_callback(callback_query: types.CallbackQuery):
            if await self.check_subscription(callback_query.from_user.id):
                await callback_query.message.delete()
                await self.bot.send_message(
                    callback_query.from_user.id,
                    "🎌 Добро пожаловать в Эмилию!\nВыберите жанр:",
                    reply_markup=self.get_main_menu(callback_query.from_user.id)
                )
            else:
                await callback_query.answer("Вы ещё не подписались на канал!", show_alert=True)

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить меню")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

        @self.dp.message_handler(lambda m: m.text in ["🔞 Включить NSFW", "🔞 Выключить NSFW"])
        async def toggle_nsfw(message: types.Message):
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"NSFW режим {status}. Доступные жанры обновлены.",
                reply_markup=self.get_main_menu(message.from_user.id)
            )

        @self.dp.message_handler(lambda m: m.text == "💎 Получить премиум")
        async def get_premium(message: types.Message):
            keyboard = InlineKeyboardMarkup()
            keyboard.add(InlineKeyboardButton("Купить премиум", callback_data="buy_premium"))
            
            await message.answer(
                "💎 Премиум-функции:\n"
                "- Доступ к эксклюзивным категориям\n"
                "- Приоритетная обработка запросов\n"
                "- Отсутствие рекламы\n\n"
                "Стоимость: 299₽/месяц",
                reply_markup=keyboard
            )

        @self.dp.message_handler(lambda m: m.text == "📊 Статистика")
        async def show_stats(message: types.Message):
            if message.from_user.id != self.admin_id:
                await message.answer("Эта команда доступна только администратору")
                return
                
            stats = await self.get_stats()
            await message.answer(
                f"📊 Статистика бота:\n\n"
                f"👥 Всего пользователей: {stats['total_users']}\n"
                f"🚀 Всего запусков: {stats['total_starts']}\n"
                f"🔥 Активных сегодня: {stats['daily_active']}"
            )

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            try:
                await self.log_command('genre_request')
                
                if not await self.check_subscription(message.from_user.id):
                    await message.answer("Для использования бота необходимо подписаться на канал!")
                    return
                
                # Проверяем премиум статус
                cursor.execute("SELECT is_premium FROM users WHERE user_id=?", (message.from_user.id,))
                result = cursor.fetchone()
                is_premium = result[0] if result else False
                
                current_genres = (self.nsfw_genres + (self.premium_genres if is_premium else [])) if self.nsfw_enabled else (self.sfw_genres + (self.premium_genres if is_premium else []))
                genre = message.text.lower()
                
                if genre not in [g.lower() for g in current_genres]:
                    await message.answer("⚠️ Пожалуйста, выберите жанр из меню")
                    return
                
                image_url = await self.get_waifu_image(genre)
                
                if not image_url:
                    await message.answer("⚠️ Не удалось загрузить изображение")
                    return
                
                await message.answer_photo(
                    image_url,
                    caption=f"Ваш {genre} арт! (NSFW: {'да' if self.nsfw_enabled else 'нет'})",
                    reply_markup=self.get_main_menu(message.from_user.id)
                )
                
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)
                await handle_genre(message)
            except Exception as e:
                logger.error(f"Ошибка обработки жанра: {str(e)}")
                await message.answer("⚠️ Произошла ошибка при загрузке")

    def run(self):
        self.register_handlers()
        executor.start_polling(
            self.dp,
            on_startup=self.on_startup,
            on_shutdown=self.on_shutdown,
            skip_updates=True,
            relax=1,
            timeout=20
        )

if __name__ == '__main__':
    bot = AnimeBot()
    bot.run()
