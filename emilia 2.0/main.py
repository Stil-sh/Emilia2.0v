import logging
import asyncio
import aiohttp
from datetime import datetime
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import RetryAfter, NetworkError
from config import BOT_TOKEN, CHANNEL_ID, ADMIN_ID

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
        
        # Жанры
        self.sfw_genres = ["waifu", "neko", "shinobu", "megumin", "awoo", "smug", "bonk", "yeet", "blush", "wave"]
        self.nsfw_genres = ["waifu", "neko", "trap", "blowjob", "cum", "lesbian", "anal", "boobs", "pussy"]
        
        self.nsfw_enabled = False
        self.session = None
        self.user_data = {}  # Хранение данных пользователей
        self.stats = {
            'total_requests': 0,
            'active_users': set(),
            'start_time': datetime.now()
        }
        self.premium_users = set()  # ID премиум пользователей
        self.channel_id = CHANNEL_ID  # ID канала для подписки

    async def on_startup(self, dp):
        self.session = aiohttp.ClientSession()
        logger.info("Бот успешно запущен")

    async def on_shutdown(self, dp):
        await self.session.close()
        logger.info("Бот остановлен")

    def get_main_menu(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        genres_to_show = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
        for genre in genres_to_show:
            keyboard.add(KeyboardButton(genre.capitalize()))
            
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(KeyboardButton(nsfw_text))
        keyboard.add(KeyboardButton("🔄 Обновить меню"))
        keyboard.add(KeyboardButton("📊 Статистика"))
        return keyboard

    async def check_subscription(self, user_id):
        try:
            member = await self.bot.get_chat_member(chat_id=self.channel_id, user_id=user_id)
            return member.status in ['member', 'administrator', 'creator']
        except Exception as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

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
            user_id = message.from_user.id
            self.stats['active_users'].add(user_id)
            
            if not await self.check_subscription(user_id):
                keyboard = InlineKeyboardMarkup()
                keyboard.add(InlineKeyboardButton("Подписаться", url=f"https://t.me/{self.channel_id}"))
                keyboard.add(InlineKeyboardButton("Проверить подписку", callback_data="check_sub"))
                await message.answer("📢 Подпишитесь на наш канал, чтобы использовать бота!", reply_markup=keyboard)
                return
                
            await message.answer(
                "🎌 Добро пожаловать в Эмилию!\nВыберите жанр:",
                reply_markup=self.get_main_menu()
            )

        @self.dp.callback_query_handler(lambda c: c.data == "check_sub")
        async def check_sub_callback(callback_query: types.CallbackQuery):
            if await self.check_subscription(callback_query.from_user.id):
                await callback_query.message.delete()
                await self.bot.send_message(
                    callback_query.from_user.id,
                    "🎉 Спасибо за подписку! Теперь вы можете использовать бота.",
                    reply_markup=self.get_main_menu()
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
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "📊 Статистика")
        async def show_stats(message: types.Message):
            if message.from_user.id != ADMIN_ID:
                await message.answer("⚠️ Эта команда доступна только администратору")
                return
                
            uptime = datetime.now() - self.stats['start_time']
            stats_text = (
                f"📊 Статистика бота:\n"
                f"⏱ Время работы: {uptime}\n"
                f"👥 Уникальных пользователей: {len(self.stats['active_users'])}\n"
                f"🔄 Всего запросов: {self.stats['total_requests']}\n"
                f"💎 Премиум пользователей: {len(self.premium_users)}"
            )
            await message.answer(stats_text)

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            user_id = message.from_user.id
            self.stats['total_requests'] += 1
            
            # Проверка подписки
            if not await self.check_subscription(user_id):
                await cmd_start(message)
                return
                
            # Проверка лимитов для обычных пользователей
            if user_id not in self.premium_users:
                current_time = datetime.now()
                last_request = self.user_data.get(user_id, {}).get('last_request')
                
                if last_request and (current_time - last_request).seconds < 30:
                    await message.answer("⏳ Обычные пользователи могут делать запросы раз в 30 секунд. Оформите премиум для снятия ограничений!")
                    return
                
                # Обновляем время последнего запроса
                if user_id not in self.user_data:
                    self.user_data[user_id] = {}
                self.user_data[user_id]['last_request'] = current_time
            
            current_genres = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
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
                reply_markup=self.get_main_menu()
            )

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
