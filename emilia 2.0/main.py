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
        try:
            member = await self.bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
            return member.status not in ['left', 'kicked']
        except exceptions.BadRequest as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False
        except Exception as e:
            logger.error(f"Неизвестная ошибка: {e}")
            return False

    async def send_subscription_request(self, message: types.Message):
        """Отправка сообщения с просьбой подписаться"""
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("👉 ПОДПИСАТЬСЯ 👈", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ Я ПОДПИСАЛСЯ", callback_data="check_sub")
        )
        
        await message.answer(
            "🔒 <b>Доступ ограничен</b>\n\n"
            "Для использования бота необходимо подписаться на наш канал:\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите кнопку <b>✅ Я ПОДПИСАЛСЯ</b>",
            reply_markup=keyboard,
            parse_mode="HTML",
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

    async def is_subscribed(self, message: types.Message) -> bool:
        """Проверка подписки с отправкой запроса если не подписан"""
        if not await self.sub_checker.check_subscription(message.from_user.id):
            await self.sub_checker.send_subscription_request(message)
            return False
        return True

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
            if not await self.is_subscribed(message):
                return
                
            await message.answer(
                "🎌 <b>Добро пожаловать!</b>\n"
                "👇 Выберите жанр из меню ниже:",
                reply_markup=self.get_main_menu(),
                parse_mode="HTML"
            )

        @self.dp.callback_query_handler(text="check_sub")
        async def check_sub_callback(call: types.CallbackQuery):
            if await self.sub_checker.check_subscription(call.from_user.id):
                await call.message.delete()
                await call.message.answer(
                    "✅ <b>Подписка подтверждена!</b>\n"
                    "Теперь вы можете использовать бота.",
                    reply_markup=self.get_main_menu(),
                    parse_mode="HTML"
                )
            else:
                await call.answer(
                    "❌ Вы не подписаны на канал!\n"
                    "Пожалуйста, подпишитесь и нажмите кнопку снова.",
                    show_alert=True
                )

        @self.dp.message_handler(lambda m: m.text in ["🔞 Включить NSFW", "🔞 Выключить NSFW"])
        async def toggle_nsfw(message: types.Message):
            if not await self.is_subscribed(message):
                return
                
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"🔞 NSFW режим {status}",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            if not await self.is_subscribed(message):
                return
                
            genres = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
            genre = message.text.lower()
            
            if genre not in [g.lower() for g in genres]:
                await message.answer("⚠ Пожалуйста, выберите жанр из меню")
                return
                
            sent_message = await message.answer("🔄 Загружаю изображение...")
            
            image_url = await self.get_waifu_image(genre)
            
            if image_url:
                try:
                    await message.answer_photo(
                        image_url,
                        caption=f"🎨 Ваш {genre} арт\n"
                               f"🔞 NSFW: {'включен' if self.nsfw_enabled else 'выключен'}",
                        reply_markup=self.get_main_menu()
                    )
                    await sent_message.delete()
                except Exception as e:
                    logger.error(f"Ошибка при отправке изображения: {e}")
                    await message.answer("⚠ Не удалось загрузить изображение")
            else:
                await message.answer("⚠ Ошибка при загрузке изображения")

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
