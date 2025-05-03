import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID
import aiohttp
import sqlite3

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# База данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Создаем таблицы
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    nsfw_enabled BOOLEAN DEFAULT FALSE
)
''')
conn.commit()

# Жанры
SFW_GENRES = {
    "waifu": "Девушки",
    "neko": "Неко",
    "shinobu": "Шинобу",
    "megumin": "Мегумин"
}

NSFW_GENRES = {
    "waifu": "Девушки (18+)",
    "neko": "Неко (18+)",
    "trap": "Трапы (18+)"
}

# Клавиатура
def get_keyboard(user_id):
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_enabled = cursor.fetchone()
    nsfw_enabled = nsfw_enabled[0] if nsfw_enabled else False
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем SFW или NSFW жанры
    genres = NSFW_GENRES if nsfw_enabled else SFW_GENRES
    for genre, label in genres.items():
        keyboard.insert(InlineKeyboardButton(label, callback_data=f"genre_{genre}"))
    
    # Кнопки управления
    keyboard.row(
        InlineKeyboardButton("🔞 NSFW" if not nsfw_enabled else "🚫 SFW", 
                          callback_data="toggle_nsfw"),
        InlineKeyboardButton("⭐ Избранное", callback_data="favorites")
    )
    return keyboard

# Получение изображения
async def get_image(genre, nsfw=False):
    api_type = "nsfw" if nsfw else "sfw"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.waifu.pics/{api_type}/{genre}",
                timeout=5
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('url')
                logger.error(f"API error: {response.status}")
    except Exception as e:
        logger.error(f"Connection error: {e}")
    return None

# Обработчики
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    await message.answer("Выбери жанр:", reply_markup=get_keyboard(user_id))

@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_image(call: types.CallbackQuery):
    user_id = call.from_user.id
    genre = call.data.split('_')[1]
    
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_enabled = cursor.fetchone()[0]
    
    image_url = await get_image(genre, nsfw_enabled)
    
    if image_url:
        try:
            if image_url.endswith('.gif'):
                await bot.send_animation(call.from_user.id, image_url, 
                                       reply_markup=get_keyboard(user_id))
            else:
                await bot.send_photo(call.from_user.id, image_url,
                                   reply_markup=get_keyboard(user_id))
        except Exception as e:
            logger.error(f"Send media error: {e}")
            await call.answer("Ошибка отправки изображения", show_alert=True)
    else:
        await call.answer("Не удалось загрузить изображение", show_alert=True)

@dp.callback_query_handler(lambda call: call.data == 'toggle_nsfw')
async def toggle_nsfw(call: types.CallbackQuery):
    user_id = call.from_user.id
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    current = cursor.fetchone()[0]
    
    new_value = not current
    cursor.execute('UPDATE users SET nsfw_enabled = ? WHERE user_id = ?', 
                 (new_value, user_id))
    conn.commit()
    
    await call.answer(f"NSFW режим {'включен' if new_value else 'выключен'}!")
    await bot.edit_message_reply_markup(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=get_keyboard(user_id)
    )

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
