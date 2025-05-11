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
        self.sfw_genres = ["waifu", "neko", "shinobu", "megumin"]
        self.nsfw_genres = ["waifu", "neko", "trap"]  # Реально работающие NSFW-жанры на waifu.pics
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
        
        # Показываем разные жанры в зависимости от режима
        genres_to_show = self.nsfw_genres if self.nsfw_enabled else self.sfw_genres
        for genre in genres_to_show:
            keyboard.add(KeyboardButton(genre.capitalize()))
            
        nsfw_text = "🔞 Включить NSFW" if not self.nsfw_enabled else "🔞 Выключить NSFW"
        keyboard.add(KeyboardButton(nsfw_text))
        keyboard.add(KeyboardButton("🔄 Обновить меню"))
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
                await message.answer(
                    "🎌 Добро пожаловать в Эмилию!\nВыберите жанр:",
                    reply_markup=self.get_main_menu()
                )
            except Exception as e:
                logger.error(f"Ошибка в /start: {str(e)}")

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

        @self.dp.message_handler()
        async def handle_genre(message: types.Message):
            try:
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
