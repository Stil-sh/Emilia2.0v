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

class ScrolllerAPI:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.base_url = "https://api.scrolller.com/api/v2/graphql"
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def get_images(self, subreddit: str, nsfw: bool = False, count: int = 1):
        """Получение изображений из субреддита на Scrolller"""
        query = {
            "query": """
                query SubredditQuery(
                    $url: String!
                    $filter: SubredditPostFilter
                    $iterator: String
                ) {
                    getSubreddit(url: $url) {
                        children(
                            limit: %d
                            filter: $filter
                            iterator: $iterator
                        ) {
                            items {
                                mediaSources {
                                    url
                                }
                                title
                                url
                            }
                        }
                    }
                }
            """ % count,
            "variables": {
                "url": f"/r/{subreddit}",
                "filter": {
                    "nsfw": nsfw
                }
            }
        }

        try:
            async with self.session.post(
                self.base_url,
                headers=self.headers,
                data=json.dumps(query)
            ) as response:
                if response.status != 200:
                    logger.error(f"Scrolller API error: {response.status}")
                    return None

                data = await response.json()
                posts = data.get('data', {}).get('getSubreddit', {}).get('children', {}).get('items', [])
                
                images = []
                for post in posts:
                    if post.get('mediaSources'):
                        for media in post['mediaSources']:
                            if media['url'].endswith(('.jpg', '.jpeg', '.png', '.gif')):
                                images.append({
                                    'url': media['url'],
                                    'title': post.get('title', ''),
                                    'post_url': post.get('url', '')
                                })
                return images

        except Exception as e:
            logger.error(f"Error fetching from Scrolller: {e}")
            return None

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.scrolller = ScrolllerAPI()
        self.sfw_subreddits = ["awwnime", "animewallpaper", "moescape"]
        self.nsfw_subreddits = ["animelegs", "animelegwear", "animearmpits"]
        self.nsfw_enabled = False

    async def on_startup(self, dispatcher):
        logger.info("Бот запущен")

    async def on_shutdown(self, dispatcher):
        await self.scrolller.session.close()
        logger.info("Бот остановлен")

    def get_main_menu(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        
        subreddits = self.nsfw_subreddits if self.nsfw_enabled else self.sfw_subreddits
        for sub in subreddits:
            keyboard.add(types.KeyboardButton(f"/{sub}"))
            
        nsfw_text = "🔞 Выключить NSFW" if self.nsfw_enabled else "🔞 Включить NSFW"
        keyboard.add(types.KeyboardButton(nsfw_text))
        keyboard.add(types.KeyboardButton("🔄 Обновить"))
        
        return keyboard

    async def send_random_image(self, message: types.Message, subreddit: str):
        """Отправка случайного изображения из субреддита"""
        loading_msg = await message.answer("🔄 Загружаю изображение с Scrolller...")
        
        images = await self.scrolller.get_images(
            subreddit=subreddit,
            nsfw=self.nsfw_enabled,
            count=5
        )
        
        if not images:
            await loading_msg.edit_text("⚠ Не удалось загрузить изображения")
            return

        image = images[0]  # Берем первое изображение из списка
        
        try:
            await self.bot.send_photo(
                chat_id=message.chat.id,
                photo=image['url'],
                caption=f"🎨 {image.get('title', '')}\n"
                       f"🔗 [Источник]({image.get('post_url', '')})\n"
                       f"🔞 NSFW: {'Да' if self.nsfw_enabled else 'Нет'}",
                parse_mode="Markdown",
                reply_markup=self.get_main_menu()
            )
            await loading_msg.delete()
        except Exception as e:
            logger.error(f"Error sending image: {e}")
            await loading_msg.edit_text("⚠ Ошибка при отправке изображения")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            await message.answer(
                "🎌 Добро пожаловать в аниме бот!\n"
                "👇 Выберите категорию из меню:",
                reply_markup=self.get_main_menu()
            )

        # Обработчики для SFW субреддитов
        for sub in self.sfw_subreddits:
            @self.dp.message_handler(commands=[sub])
            async def handle_sfw_sub(message: types.Message):
                if self.nsfw_enabled:
                    await message.answer("⚠ Сначала отключите NSFW режим!")
                    return
                subreddit = message.text[1:]  # Убираем / из команды
                await self.send_random_image(message, subreddit)

        # Обработчики для NSFW субреддитов
        for sub in self.nsfw_subreddits:
            @self.dp.message_handler(commands=[sub])
            async def handle_nsfw_sub(message: types.Message):
                if not self.nsfw_enabled:
                    await message.answer("⚠ Сначала включите NSFW режим!")
                    return
                subreddit = message.text[1:]  # Убираем / из команды
                await self.send_random_image(message, subreddit)

        @self.dp.message_handler(lambda m: m.text in ["🔞 Включить NSFW", "🔞 Выключить NSFW"])
        async def toggle_nsfw(message: types.Message):
            self.nsfw_enabled = not self.nsfw_enabled
            status = "включен" if self.nsfw_enabled else "выключен"
            await message.answer(
                f"🔞 NSFW режим {status}",
                reply_markup=self.get_main_menu()
            )

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить")
        async def refresh_menu(message: types.Message):
            await cmd_start(message)

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
