import logging
import aiohttp
import json
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

class ImageLoader:
    def __init__(self):
        self.session = None

    async def init_session(self):
        """Инициализация сессии"""
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Закрытие сессии"""
        if self.session:
            await self.session.close()

    async def get_waifu_image(self, category: str):
        """Получение случайного изображения от waifu.pics"""
        try:
            async with self.session.get(f"https://api.waifu.pics/{category}/waifu") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('url')
        except Exception as e:
            logger.error(f"Ошибка при получении изображения: {e}")
        return None

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.sub_checker = SubscriptionChecker(self.bot)
        self.image_loader = ImageLoader()
        self.nsfw_enabled = False

    async def on_startup(self, dispatcher):
        await self.image_loader.init_session()
        logger.info("Бот запущен")

    async def on_shutdown(self, dispatcher):
        await self.image_loader.close_session()
        logger.info("Бот остановлен")

    async def is_subscribed(self, message: types.Message) -> bool:
        """Проверка подписки"""
        if not await self.sub_checker.check_subscription(message.from_user.id):
            await self.sub_checker.send_subscription_request(message)
            return False
        return True

    def get_main_menu(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        buttons = [
            "🎲 Случайное изображение",
            "🔞 Включить NSFW" if not self.nsfw_enabled else "🔞 Выключить NSFW",
            "🔄 Обновить меню"
        ]
        keyboard.add(*buttons)
        return keyboard

    async def send_random_image(self, message: types.Message):
        """Отправка случайного изображения"""
        loading_msg = await message.answer("🔄 Загружаю изображение...")
        
        category = "nsfw" if self.nsfw_enabled else "sfw"
        image_url = await self.image_loader.get_waifu_image(category)
        
        if image_url:
            try:
                await message.answer_photo(
                    photo=image_url,
                    caption=f"Случайное аниме изображение\n"
                           f"🔞 NSFW: {'Да' if self.nsfw_enabled else 'Нет'}",
                    reply_markup=self.get_main_menu()
                )
                await loading_msg.delete()
            except Exception as e:
                logger.error(f"Ошибка отправки изображения: {e}")
                await loading_msg.edit_text("⚠ Ошибка при отправке изображения")
        else:
            await loading_msg.edit_text("⚠ Не удалось загрузить изображение")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            if not await self.is_subscribed(message):
                return
            await message.answer(
                "🎌 Добро пожаловать в аниме бот!\n"
                "👇 Выберите действие:",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "🎲 Случайное изображение")
        async def random_image_handler(message: types.Message):
            if not await self.is_subscribed(message):
                return
            await self.send_random_image(message)

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

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить меню")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

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
                    "❌ Вы не подписаны на канал!",
                    show_alert=True
                )

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
