import logging
import asyncio
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import RetryAfter, NetworkError
from config import BOT_TOKEN

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
        self.genres = ["Waifu", "Neko", "Shinobu", "Megumin", "NSFW режим"]
        self.nsfw_enabled = False

    def get_main_menu(self):
        """Создает статичную клавиатуру"""
        keyboard = ReplyKeyboardMarkup(
            resize_keyboard=True,
            row_width=2,
            one_time_keyboard=False
        )
        # Первые 4 кнопки
        for genre in self.genres[:4]:
            keyboard.add(KeyboardButton(genre))
        # Кнопка NSFW отдельно
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(KeyboardButton(nsfw_text))
        return keyboard

    async def on_startup(self, dp):
        logger.info("Бот успешно запущен")

    async def on_shutdown(self, dp):
        logger.info("Бот остановлен")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start'])
        async def cmd_start(message: types.Message):
            try:
                await message.answer(
                    "🎌 Добро пожаловать в аниме-бот!\n"
                    "Выберите жанр:",
                    reply_markup=self.get_main_menu()
                )
            except Exception as e:
                logger.error(f"Start error: {e}")

        @self.dp.message_handler(lambda message: message.text in self.genres[:4])
        async def process_genre(message: types.Message):
            try:
                genre = message.text.lower()
                # Здесь должен быть ваш код получения изображения
                # Например:
                image_url = f"https://api.waifu.pics/sfw/{genre}"
                
                await message.answer_photo(
                    image_url,
                    caption=f"Ваш {genre} арт!",
                    reply_markup=self.get_main_menu()
                )
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)
                await self.process_genre(message)
            except NetworkError:
                await message.answer("⚠️ Ошибка сети. Попробуйте позже.")
            except Exception as e:
                logger.error(f"Genre error: {e}")
                await message.answer("⚠️ Произошла ошибка.")

        @self.dp.message_handler(lambda message: "NSFW" in message.text)
        async def toggle_nsfw(message: types.Message):
            try:
                self.nsfw_enabled = not self.nsfw_enabled
                await message.answer(
                    f"NSFW режим {'включен' if self.nsfw_enabled else 'выключен'}",
                    reply_markup=self.get_main_menu()
                )
            except Exception as e:
                logger.error(f"NSFW toggle error: {e}")

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
