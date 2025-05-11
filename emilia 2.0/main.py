import logging
import aiohttp
import json
from aiogram import Bot, Dispatcher, types
from aiogram.utils import exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, CHANNEL_ID, CHANNEL_LINK, SCROLLLER_API, HEADERS, CATEGORIES

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SubscriptionManager:
    def __init__(self, bot):
        self.bot = bot
        self.cache = {}

    async def verify_subscription(self, user_id: int) -> bool:
        try:
            member = await self.bot.get_chat_member(CHANNEL_ID, user_id)
            return member.status not in ['left', 'kicked']
        except exceptions.BadRequest as e:
            logger.error(f"Subscription check error: {e}")
            return False

    async def request_subscription(self, message: types.Message):
        keyboard = InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            InlineKeyboardButton("👉 ПОДПИСАТЬСЯ", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ ПРОВЕРИТЬ ПОДПИСКУ", callback_data="check_sub")
        )
        
        await message.answer(
            "🔒 Для доступа требуется подписка!\n"
            f"Канал: {CHANNEL_LINK}\n\n"
            "После подписки нажмите кнопку проверки",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

class ScrolllerClient:
    def __init__(self):
        self.session = aiohttp.ClientSession()
        
    async def fetch_content(self, subreddit: str, nsfw: bool, count: int = 5):
        query = {
            "query": f"""
                query SubredditQuery($url: String!, $filter: SubredditPostFilter) {{
                    getSubreddit(url: $url) {{
                        children(limit: {count}, filter: $filter) {{
                            items {{
                                mediaSources {{ url }},
                                title,
                                url
                            }}
                        }}
                    }}
                }}
            """,
            "variables": {
                "url": f"/r/{subreddit}",
                "filter": {"nsfw": nsfw}
            }
        }

        try:
            async with self.session.post(
                SCROLLLER_API,
                headers=HEADERS,
                data=json.dumps(query)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return self.parse_content(data)
                logger.error(f"API Error: {response.status}")
        except Exception as e:
            logger.error(f"Scrolller error: {e}")
        return None

    @staticmethod
    def parse_content(data: dict) -> list:
        items = data.get('data', {}).get('getSubreddit', {}).get('children', {}).get('items', [])
        return [
            {
                "media": [m['url'] for m in item.get('mediaSources', [])],
                "title": item.get('title', ''),
                "url": item.get('url', '')
            } for item in items if item.get('mediaSources')
        ]

class AnimeBot:
    def __init__(self):
        self.bot = Bot(token=BOT_TOKEN)
        self.dp = Dispatcher(self.bot)
        self.sub_manager = SubscriptionManager(self.bot)
        self.scrolller = ScrolllerClient()
        self.current_mode = "sfw"

    async def shutdown(self, _):
        await self.scrolller.session.close()
        logger.info("Bot stopped")

    def create_menu(self):
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        current_cat = CATEGORIES[self.current_mode]
        
        # Добавляем кнопки для субреддитов
        for sub in current_cat['subreddits']:
            keyboard.add(types.KeyboardButton(f"/{sub}"))
            
        # Кнопки управления
        mode_button = "🔞 NSFW" if self.current_mode == "sfw" else "🔒 SFW"
        keyboard.add(
            types.KeyboardButton(mode_button),
            types.KeyboardButton("🔄 Обновить")
        )
        return keyboard

    async def send_media(self, message: types.Message, subreddit: str):
        if not await self.sub_manager.verify_subscription(message.from_user.id):
            await self.sub_manager.request_subscription(message)
            return

        loading_msg = await message.answer("🔄 Загрузка контента...")
        content = await self.scrolller.fetch_content(
            subreddit=subreddit,
            nsfw=CATEGORIES[self.current_mode]['nsfw']
        )

        if not content:
            await loading_msg.edit_text("⚠ Ошибка загрузки")
            return

        try:
            media = content[0]['media'][0]
            await message.answer_photo(
                photo=media,
                caption=f"🎴 {content[0]['title']}\n🔗 {content[0]['url']}",
                reply_markup=self.create_menu()
            )
            await loading_msg.delete()
        except Exception as e:
            logger.error(f"Send media error: {e}")
            await loading_msg.edit_text("⚠ Ошибка отправки")

    def register_handlers(self):
        @self.dp.message_handler(commands=['start', 'menu'])
        async def start_handler(message: types.Message):
            if await self.sub_manager.verify_subscription(message.from_user.id):
                await message.answer("Выберите категорию:", reply_markup=self.create_menu())
            else:
                await self.sub_manager.request_subscription(message)

        @self.dp.callback_query_handler(text="check_sub")
        async def check_sub_callback(call: types.CallbackQuery):
            if await self.sub_manager.verify_subscription(call.from_user.id):
                await call.message.delete()
                await call.message.answer("Доступ разрешен!", reply_markup=self.create_menu())
            else:
                await call.answer("❌ Подписка не обнаружена!", show_alert=True)

        @self.dp.message_handler(lambda m: m.text in ["🔞 NSFW", "🔒 SFW"])
        async def toggle_mode(message: types.Message):
            self.current_mode = "nsfw" if self.current_mode == "sfw" else "sfw"
            await message.answer(f"Режим: {CATEGORIES[self.current_mode]['name']}", reply_markup=self.create_menu())

        @self.dp.message_handler(lambda m: m.text.startswith('/'))
        async def subreddit_handler(message: types.Message):
            subreddit = message.text[1:]
            if subreddit in CATEGORIES[self.current_mode]['subreddits']:
                await self.send_media(message, subreddit)
            else:
                await message.answer("⚠ Неизвестная категория!")

        @self.dp.message_handler(lambda m: m.text == "🔄 Обновить")
        async def refresh_handler(message: types.Message):
            await start_handler(message)

if __name__ == '__main__':
    bot = AnimeBot()
    bot.dp.register_message_handler(bot.refresh_handler)
    executor.start_polling(bot.dp, on_shutdown=bot.shutdown, skip_updates=True)
