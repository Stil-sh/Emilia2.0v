import logging
import aiohttp
import json
import random
from aiogram import Bot, Dispatcher, types, executor
from aiogram.utils import exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_LINK, USER_CATEGORIES, SCROLLLER_MAPPING

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubscriptionManager:
    def __init__(self, bot):
        self.bot = bot
        self.sub_cache = {}

    async def check_subscription(self, user_id: int) -> bool:
        if user_id in self.sub_cache:
            return self.sub_cache[user_id]
            
        try:
            member = await self.bot.get_chat_member(CHANNEL_ID, user_id)
            result = member.status not in ['left', 'kicked']
            self.sub_cache[user_id] = result
            return result
        except exceptions.BadRequest as e:
            logger.error(f"Subscription check error: {e}")
            return False

    async def request_subscription(self, message: types.Message):
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("👉 Подписаться", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")
        )
        await message.answer(
            "🔒 Для доступа к контенту необходимо подписаться на наш канал:\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите кнопку проверки",
            reply_markup=markup,
            disable_web_page_preview=True
        )

class ScrolllerAPI:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.headers = {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    async def fetch_content(self, subreddit: str):
        """Улучшенный метод с логированием запросов"""
        query = {
            "query": """query SubredditQuery($url: String!) {
                getSubreddit(url: $url) {
                    children(limit: 25, iterator: null) {
                        items {
                            mediaSources {
                                url
                                type
                            }
                            title
                            url
                        }
                        iterator
                    }
                }
            }""",
            "variables": {"url": f"/r/{subreddit}"}
        }

        try:
            logger.info(f"Запрос к API для субреддита: {subreddit}")
            async with self.session.post(
                "https://api.scrolller.com/api/v2/graphql",
                json=query,
                headers=self.headers
            ) as response:
                if response.status != 200:
                    logger.error(f"API Error: {response.status}")
                    return None
                
                raw_data = await response.text()
                logger.debug(f"Raw API response: {raw_data}")
                data = json.loads(raw_data)
                return self.parse_content(data)
                
        except Exception as e:
            logger.error(f"Scrolller error: {str(e)}")
            return None

    def parse_content(self, data: dict) -> list:
        """Детальный парсинг с проверкой структуры"""
        try:
            if not data.get('data', {}).get('getSubreddit'):
                logger.error("Некорректная структура ответа API")
                return []

            items = data['data']['getSubreddit']['children']['items']
            valid_posts = []
            
            for item in items:
                try:
                    media_list = [
                        m['url'] for m in item['mediaSources']
                        if m['type'] in ['IMAGE', 'GIF']
                        and any(ext in m['url'].lower() for ext in ['.jpg', '.jpeg', '.png', '.gif'])
                    ]
                    if media_list:
                        valid_posts.append({
                            'title': item.get('title', 'Без названия'),
                            'media': media_list,
                            'url': item.get('url', '')
                        })
                except KeyError as e:
                    logger.warning(f"Пропущен пост из-за ошибки: {str(e)}")
            
            logger.info(f"Найдено {len(valid_posts)} валидных постов")
            return valid_posts
            
        except Exception as e:
            logger.error(f"Critical parsing error: {str(e)}")
            return []

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.sub_manager = SubscriptionManager(self.bot)
        self.scrolller = ScrolllerAPI()

    async def shutdown(self, _):
        await self.scrolller.session.close()
        logger.info("Бот остановлен")

    def generate_menu(self):
        markup = InlineKeyboardMarkup(row_width=1)
        for category in USER_CATEGORIES:
            btn_text = f"{category} {'🔓' if USER_CATEGORIES[category]['nsfw'] else '🔒'}"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"cat_{category}"))
        return markup

    async def send_content(self, message: types.Message, subreddit: str):
        """Улучшенная обработка контента с повтором"""
        if not await self.sub_manager.check_subscription(message.from_user.id):
            await self.sub_manager.request_subscription(message)
            return

        loading_msg = await message.answer("🔄 Поиск контента...")
        
        try:
            content = await self.scrolller.fetch_content(subreddit)
            if not content:
                await loading_msg.edit_text(
                    "😢 В этой категории пока нет контента\n"
                    "Попробуйте:\n"
                    "1. Выбрать другую подкатегорию\n"
                    "2. Проверить название субреддита\n"
                    "3. Попробовать позже"
                )
                return

            post = random.choice(content)
            media = post['media'][0]
            
            await message.answer_photo(
                photo=media,
                caption=f"🎴 {post['title']}\n🔗 {post['url']}",
                reply_markup=self.generate_menu()
            )
            await loading_msg.delete()
            
        except Exception as e:
            logger.error(f"Content send error: {str(e)}")
            await loading_msg.edit_text("⚠ Произошла непредвиденная ошибка")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            if await self.sub_manager.check_subscription(message.from_user.id):
                await message.answer("🏮 Добро пожаловать! Выберите категорию:", reply_markup=self.generate_menu())
            else:
                await self.sub_manager.request_subscription(message)

        @self.dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
        async def handle_category(callback: types.CallbackQuery):
            category_name = callback.data[4:]
            category = USER_CATEGORIES.get(category_name)
            
            if not category:
                await callback.answer("⚠ Ошибка категории!")
                return

            markup = InlineKeyboardMarkup(row_width=1)
            for sub_name, sub_list in category["Подкатегории"].items():
                for key in sub_list:
                    tech_name = SCROLLLER_MAPPING.get(key)
                    if tech_name:
                        markup.add(InlineKeyboardButton(sub_name, callback_data=f"sub_{tech_name}"))
            
            markup.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
            await callback.message.edit_text(
                f"📂 {category_name}\nВыберите подкатегорию:", 
                reply_markup=markup
            )

        @self.dp.callback_query_handler(lambda c: c.data.startswith('sub_'))
        async def handle_subcategory(callback: types.CallbackQuery):
            subreddit = callback.data[4:]
            await self.send_content(callback.message, subreddit)

        @self.dp.callback_query_handler(text="check_sub")
        async def check_sub(callback: types.CallbackQuery):
            if await self.sub_manager.check_subscription(callback.from_user.id):
                await callback.message.delete()
                await callback.message.answer("✅ Доступ разрешен!", reply_markup=self.generate_menu())
            else:
                await callback.answer("❌ Подписка не обнаружена!", show_alert=True)

        @self.dp.callback_query_handler(text="back_main")
        async def back_main(callback: types.CallbackQuery):
            await callback.message.edit_text("🏮 Выберите категорию:", reply_markup=self.generate_menu())

if __name__ == '__main__':
    bot = AnimeBot()
    bot.register_handlers()
    executor.start_polling(bot.dp, on_shutdown=bot.shutdown, skip_updates=True)
if __name__ == '__main__':
    bot = AnimeBot()
    bot.register_handlers()
    executor.start_polling(bot.dp, on_shutdown=bot.shutdown, skip_updates=True)
