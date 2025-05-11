import logging
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.dispatcher import filters
from aiogram.utils import exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_LINK

# Настройка логгирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubscriptionChecker:
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    async def check_subscription(self, user_id: int) -> bool:
        """Проверка подписки пользователя на канал"""
        if user_id in self.cache:
            return self.cache[user_id]

        try:
            member = await self.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            result = member.status not in ['left', 'kicked']
            self.cache[user_id] = result
            return result
            
        except exceptions.BadRequest as e:
            if "bot is not a member" in str(e).lower():
                logger.error("Бот не является участником канала!")
            return True
        except exceptions.ChatNotFound:
            logger.error("Канал не найден!")
            return True
        except exceptions.Unauthorized:
            logger.error("Бот заблокирован пользователем")
            return False
        except exceptions.TelegramAPIError as e:
            logger.error(f"Ошибка API: {e}")
            return True

    async def send_subscription_request(self, message: types.Message):
        """Отправка сообщения с просьбой подписаться"""
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("📢 Подписаться", url=CHANNEL_LINK))
        keyboard.add(InlineKeyboardButton("✅ Я подписался", callback_data="check_sub"))
        
        await message.answer(
            "📛 Для доступа к боту подпишитесь на наш канал!\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.sub_checker = SubscriptionChecker(self.bot)
        self.sfw_genres = ["waifu", "neko", "shinobu", "megumin"]
        self.nsfw_genres = ["waifu", "neko", "trap"]
        self.nsfw_enabled = False
        self.session = aiohttp.ClientSession()

    async def on_startup(self, dispatcher):
        logger.info("Бот запущен")

    async def on_shutdown(self, dispatcher):
        await self.session.close()
        logger.info("Бот остановлен")

    def get_main_menu(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        genres = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
        
        for genre in genres:
            keyboard.add(types.KeyboardButton(genre.capitalize()))
            
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(types.KeyboardButton(nsfw_text))
        keyboard.add(types.KeyboardButton("🔄 Обновить"))
        
        return keyboard

    async def get_waifu_image(self, genre: str):
        """Получение изображения от waifu.pics API"""
        try:
            category = 'nsfw' if self.nsfw_enabled else 'sfw'
            url = f"https://api.waifu.pics/{category}/{genre}"
            
            async with self.session.get(url) as response:
                if response.status != 200:
                    logger.error(f"API вернул статус {response.status}")
                    return None
                
                data = await response.json()
                return data.get('url')
                
        except Exception as e:
            logger.error(f"Ошибка при получении изображения: {e}")
            return None

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            # Проверка подписки перед выполнением команды
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            await message.answer(
                "🎌 Добро пожаловать!\nВыберите жанр:",
                reply_markup=self.get_main_menu()
            )

        @self.dp.callback_query_handler(text="check_sub")
        async def check_sub_callback(call: types.CallbackQuery):
            # Проверка подписки при нажатии кнопки "Я подписался"
            if await self.sub_checker.check_subscription(call.from_user.id):
                await call.message.delete()
                await call.message.answer(
                    "✅ Спасибо за подписку! Теперь вы можете использовать бота.",
                    reply_markup=self.get_main_menu()
                )
            else:
                await call.answer("❌ Вы ещё не подписались!", show_alert=True)

        @self.dp.message_handler(lambda m: m.text in ["🔞 Включить NSFW", "🔞 Выключить NSFW"])
        async def toggle_nsfw(message: types.Message):
            # Проверка подписки перед изменением режима NSFW
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"NSFW режим {status}",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить")
        async def refresh_menu(message: types.Message):
            # Проверка подписки перед обновлением меню
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
            await cmd_start(message)

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            # Проверка подписки перед обработкой жанра
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            genres = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
            genre = message.text.lower()
            
            if genre not in [g.lower() for g in genres]:
                await message.answer("⚠ Выберите жанр из меню")
                return
                
            sent_message = await message.answer("🔄 Загружаю изображение...")
            
            image_url = await self.get_waifu_image(genre)
            
            if image_url:
                try:
                    await message.answer_photo(
                        image_url,
                        caption=f"Ваш {genre} арт! (NSFW: {'да' if self.nsfw_enabled else 'нет'})",
                        reply_markup=self.get_main_menu()
                    )
                    await sent_message.delete()
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения: {e}")
                    await message.answer("⚠ Не удалось загрузить изображение")
            else:
                await message.answer("⚠ Произошла ошибка при загрузке изображения")

    def run(self):
        self.register_handlers()
        from aiogram import executor
        executor.start_polling(
            self.dp,
            on_startup=self.on_startup,
            on_shutdown=self.on_shutdown,
            skip_updates=True
        )

if __name__ == '__main__':
    bot = AnimeBot()
    bot.run()
