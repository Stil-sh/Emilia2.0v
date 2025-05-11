import logging
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

    async def on_startup(self, dispatcher):
        logger.info("Бот запущен")

    async def on_shutdown(self, dispatcher):
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

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            await message.answer(
                "🎌 Добро пожаловать!\nВыберите жанр:",
                reply_markup=self.get_main_menu()
            )

        @self.dp.callback_query_handler(text="check_sub")
        async def check_sub_callback(call: types.CallbackQuery):
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
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"NSFW режим {status}",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            genres = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
            genre = message.text.lower()
            
            if genre not in [g.lower() for g in genres]:
                await message.answer("⚠ Выберите жанр из меню")
                return
                
            await message.answer("🔄 Загружаю изображение...")
            # Здесь должна быть логика загрузки изображения

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
