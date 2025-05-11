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

class ScrolllerAPI:
    def __init__(self):
        self.session = None

    async def init_session(self):
        """Инициализация сессии при запуске"""
        self.session = aiohttp.ClientSession()

    async def close_session(self):
        """Закрытие сессии при остановке"""
        if self.session:
            await self.session.close()

    async def get_images(self, subreddit: str, nsfw: bool = False, count: int = 1):
        """Получение изображений из субреддита на Scrolller"""
        if not self.session:
            await self.init_session()

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
                "https://api.scrolller.com/api/v2/graphql",
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
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
        self.sub_checker = SubscriptionChecker(self.bot)
        self.scrolller = ScrolllerAPI()
        self.sfw_subreddits = ["awwnime", "animewallpaper", "moescape"]
        self.nsfw_subreddits = ["animelegs", "animelegwear", "animearmpits"]
        self.nsfw_enabled = False

    async def on_startup(self, dispatcher):
        await self.scrolller.init_session()
        logger.info("Бот запущен")

    async def on_shutdown(self, dispatcher):
        await self.scrolller.close_session()
        logger.info("Бот остановлен")

    async def is_subscribed(self, message: types.Message) -> bool:
        """Проверка подписки с отправкой запроса если не подписан"""
        if not await self.sub_checker.check_subscription(message.from_user.id):
            await self.sub_checker.send_subscription_request(message)
            return False
        return True

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
        if not await self.is_subscribed(message):
            return
            
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
            if not await self.is_subscribed(message):
                return
                
            await message.answer(
                "🎌 <b>Добро пожаловать в аниме бот!</b>\n"
                "👇 Выберите категорию из меню:",
                reply_markup=self.get_main_menu(),
                parse_mode="HTML"
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
