import logging
import aiohttp
import json
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
        """Проверка подписки на канал"""
        if user_id in self.sub_cache:
            return self.sub_cache[user_id]
            
        try:
            member = await self.bot.get_chat_member(CHANNEL_ID, user_id)
            result = member.status not in ['left', 'kicked']
            self.sub_cache[user_id] = result
            return result
        except exceptions.BadRequest as e:
            logger.error(f"Ошибка проверки подписки: {e}")
            return False

    async def send_sub_request(self, message: types.Message):
        """Отправка запроса на подписку"""
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("👉 Подписаться", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ Проверить подписку", callback_data="check_sub")
        )
        await message.answer(
            "🔒 Для доступа к контенту необходимо подписаться на канал:\n"
            f"{CHANNEL_LINK}\n\n"
            "После подписки нажмите кнопку проверки",
            reply_markup=markup,
            disable_web_page_preview=True
        )

class ScrolllerClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        self.base_url = "https://api.scrolller.com/api/v2/graphql"
        self.headers = {"Content-Type": "application/json"}

    async def fetch_content(self, subreddit: str, nsfw: bool):
        """Получение контента из субреддита"""
        query = {
            "query": """query SubredditQuery($url: String!) {
                getSubreddit(url: $url) {
                    children(limit: 10) {
                        items {
                            mediaSources { url }
                            title
                            url
                        }
                    }
                }
            }""",
            "variables": {"url": f"/r/{subreddit}"}
        }

        try:
            async with self.session.post(
                self.base_url,
                json=query,
                headers=self.headers
            ) as response:
                if response.status != 200:
                    return None
                return await self.parse_response(await response.json(), nsfw)
        except Exception as e:
            logger.error(f"Ошибка Scrolller: {e}")
            return None

    @staticmethod
    def parse_response(data: dict, nsfw: bool) -> list:
        """Парсинг ответа API"""
        items = data.get('data', {}).get('getSubreddit', {}).get('children', {}).get('items', [])
        valid_content = []
        
        for item in items:
            media = [m['url'] for m in item.get('mediaSources', []) if m['url'].endswith(('.jpg', '.jpeg', '.png'))]
            if media:
                valid_content.append({
                    'title': item.get('title', 'Без названия'),
                    'media': media,
                    'url': item.get('url', ''),
                    'nsfw': nsfw
                })
        return valid_content

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.sub_manager = SubscriptionManager(self.bot)
        self.scrolller = ScrolllerClient()
        self.user_states = {}

    async def shutdown(self, _):
        await self.scrolller.session.close()
        logger.info("Бот остановлен")

    def create_main_menu(self):
        """Генерация главного меню"""
        markup = InlineKeyboardMarkup(row_width=1)
        for category in USER_CATEGORIES:
            btn_text = f"{category} {'🔓' if USER_CATEGORIES[category]['nsfw'] else '🔒'}"
            markup.add(InlineKeyboardButton(btn_text, callback_data=f"cat_{category}"))
        return markup

    async def send_category_content(self, message: types.Message, subreddit: str, nsfw: bool):
        """Отправка контента пользователю"""
        if not await self.sub_manager.check_subscription(message.from_user.id):
            await self.sub_manager.send_sub_request(message)
            return

        loading_msg = await message.answer("🔄 Загрузка контента...")
        content = await self.scrolller.fetch_content(subreddit, nsfw)
        
        if not content:
            await loading_msg.edit_text("⚠ Контент не найден")
            return

        try:
            post = random.choice(content)
            await message.answer_photo(
                photo=post['media'][0],
                caption=f"🎴 {post['title']}\n🔗 {post['url']}",
                reply_markup=self.create_main_menu()
            )
            await loading_msg.delete()
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")
            await loading_msg.edit_text("⚠ Ошибка загрузки контента")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def cmd_start(message: types.Message):
            if await self.sub_manager.check_subscription(message.from_user.id):
                await message.answer("Выберите категорию:", reply_markup=self.create_main_menu())
            else:
                await self.sub_manager.send_sub_request(message)

        @self.dp.callback_query_handler(lambda c: c.data.startswith('cat_'))
        async def handle_category(callback: types.CallbackQuery):
            category_name = callback.data[4:]
            category = USER_CATEGORIES.get(category_name)
            
            if not category:
                await callback.answer("⚠ Категория не найдена!")
                return
                
            if category['nsfw'] and not await self.sub_manager.check_subscription(callback.from_user.id):
                await callback.answer("🔞 Требуется проверка возраста!", show_alert=True)
                return

            markup = InlineKeyboardMarkup(row_width=1)
            for sub_name, sub_list in category['Подкатегории'].items():
                for key in sub_list:
                    tech_name = SCROLLLER_MAPPING.get(key)
                    if tech_name:
                        markup.add(InlineKeyboardButton(sub_name, callback_data=f"sub_{tech_name}"))
            
            markup.add(InlineKeyboardButton("🔙 Назад", callback_data="back_main"))
            await callback.message.edit_text(
                f"Категория: {category_name}\nВыберите подкатегорию:",
                reply_markup=markup
            )

        @self.dp.callback_query_handler(lambda c: c.data.startswith('sub_'))
        async def handle_subcategory(callback: types.CallbackQuery):
            subreddit = callback.data[4:]
            category = next((cat for cat in USER_CATEGORIES.values() if any(subreddit in sub_list for sub_list in cat['Подкатегории'].values())), None)
            
            if not category:
                await callback.answer("⚠ Ошибка подкатегории!")
                return
                
            await self.send_category_content(callback.message, subreddit, category['nsfw'])

        @self.dp.callback_query_handler(text="check_sub")
        async def check_subscription(callback: types.CallbackQuery):
            if await self.sub_manager.check_subscription(callback.from_user.id):
                await callback.message.delete()
                await callback.message.answer("✅ Доступ разрешен!", reply_markup=self.create_main_menu())
            else:
                await callback.answer("❌ Вы не подписаны!", show_alert=True)

        @self.dp.callback_query_handler(text="back_main")
        async def back_to_main(callback: types.CallbackQuery):
            await callback.message.edit_text("Выберите категорию:", reply_markup=self.create_main_menu())

if __name__ == '__main__':
    bot = AnimeBot()
    bot.register_handlers()
    executor.start_polling(bot.dp, on_shutdown=bot.shutdown, skip_updates=True)
