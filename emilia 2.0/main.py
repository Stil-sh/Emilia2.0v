import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.exceptions import TelegramBadRequest, TelegramAPIError
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
            
        except TelegramBadRequest as e:
            if "bot is not a member" in str(e).lower():
                logger.error("Бот не является участником канала!")
            return True
        except TelegramAPIError as e:
            logger.error(f"Ошибка API: {e}")
            return True

    async def send_subscription_request(self, message: types.Message):
        """Отправка сообщения с просьбой подписаться"""
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=CHANNEL_LINK)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
        ])
        
        await message.answer(
            "📛 Для доступа к боту подпишитесь на наш канал!\n"
            "После подписки нажмите кнопку ниже:",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(bot=self.bot)  # Исправлено: передаем бота в Dispatcher
        self.sub_checker = SubscriptionChecker(self.bot)
        self.sfw_genres = ["waifu", "neko", "shinobu", "megumin"]
        self.nsfw_genres = ["waifu", "neko", "trap"]
        self.nsfw_enabled = False

    async def on_startup(self):
        logger.info("Бот запущен")

    async def on_shutdown(self):
        logger.info("Бот остановлен")

    def get_main_menu(self):
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text=genre.capitalize()) for genre in 
                 (self.nsfw_genres if self.nsfw_enabled else self.sfw_genres)],
                [
                    types.KeyboardButton(
                        text="🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
                    ),
                    types.KeyboardButton(text="🔄 Обновить")
                ]
            ],
            resize_keyboard=True
        )
        return keyboard

    def register_handlers(self):
        @self.dp.message(Command("start", "menu"))
        async def cmd_start(message: types.Message):
            if not await self.sub_checker.check_subscription(message.from_user.id):
                await self.sub_checker.send_subscription_request(message)
                return
                
            await message.answer(
                "🎌 Добро пожаловать!\nВыберите жанр:",
                reply_markup=self.get_main_menu()
            )

        @self.dp.callback_query(lambda c: c.data == "check_sub")
        async def check_sub_callback(callback: types.CallbackQuery):
            if await self.sub_checker.check_subscription(callback.from_user.id):
                await callback.message.delete()
                await callback.message.answer(
                    "✅ Спасибо за подписку! Теперь вы можете использовать бота.",
                    reply_markup=self.get_main_menu()
                )
            else:
                await callback.answer("❌ Вы ещё не подписались!", show_alert=True)

        @self.dp.message(
            lambda m: m.text in ["🔞 Включить NSFW", "🔞 Выключить NSFW"]
        )
        async def toggle_nsfw(message: types.Message):
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"NSFW режим {status}",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message(lambda m: m.text == "🔄 Обновить")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

        @self.dp.message()
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

    async def run(self):
        await self.on_startup()
        self.register_handlers()
        await self.dp.start_polling(self.bot)
        await self.on_shutdown()

if __name__ == '__main__':
    bot = AnimeBot()
    import asyncio
    asyncio.run(bot.run())
