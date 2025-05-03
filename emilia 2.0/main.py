import logging
import asyncio
import aiohttp
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
        self.genres = ["Waifu", "Neko", "Shinobu", "Megumin"]
        self.nsfw_enabled = False
        self.session = None

    async def on_startup(self, dp):
        self.session = aiohttp.ClientSession()
        logger.info("Бот успешно запущен")

    async def on_shutdown(self, dp):
        await self.session.close()
        logger.info("Бот остановлен")

    def get_main_menu(self):
        keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        for genre in self.genres:
            keyboard.add(KeyboardButton(genre))
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(KeyboardButton(nsfw_text))
        return keyboard

    async def get_waifu_image(self, genre: str):
        try:
            category = 'nsfw' if self.nsfw_enabled else 'sfw'
            url = f"https://api.waifu.pics/{category}/{genre.lower()}"
            
            async with self.session.get(url, timeout=5) as response:
                if response.status != 200:
                    raise NetworkError(f"API error: {response.status}")
                
                data = await response.json()
                return data['url']
                
        except Exception as e:
            logger.error(f"API request failed: {e}")
            return None

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            try:
                await message.answer(
                    "🎌 Добро пожаловать в аниме-бот!\nВыберите жанр:",
                    reply_markup=self.get_main_menu()
                )
            except Exception as e:
                logger.error(f"Start error: {e}")

        @self.dp.message_handler(lambda m: m.text in self.genres or "NSFW" in m.text)
        async def handle_buttons(message: types.Message):
            try:
                if "NSFW" in message.text:
                    self.nsfw_enabled = not self.nsfw_enabled
                    await message.answer(
                        f"NSFW режим {'включен' if self.nsfw_enabled else 'выключен'}",
                        reply_markup=self.get_main_menu()
                    )
                    return

                genre = message.text.lower()
                image_url = await self.get_waifu_image(genre)
                
                if not image_url:
                    await message.answer("⚠️ Не удалось загрузить изображение")
                    return
                
                await message.answer_photo(
                    image_url,
                    caption=f"Ваш {genre} арт!",
                    reply_markup=self.get_main_menu()
                )
                
            except RetryAfter as e:
                await asyncio.sleep(e.timeout)
                await handle_buttons(message)
            except Exception as e:
                logger.error(f"Button handler error: {e}")
                await message.answer("⚠️ Произошла ошибка")

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
