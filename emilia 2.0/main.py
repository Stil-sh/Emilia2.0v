import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
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
SFW_GENRES = ["waifu", "neko", "shinobu", "megumin"]
NSFW_GENRES = ["waifu", "neko", "trap"]

# Клавиатура
def get_keyboard(user_id):
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_enabled = cursor.fetchone()
    nsfw_enabled = nsfw_enabled[0] if nsfw_enabled else False
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Добавляем SFW или NSFW жанры
    genres = NSFW_GENRES if nsfw_enabled else SFW_GENRES
    for genre in genres:
        keyboard.insert(KeyboardButton(genre.capitalize()))
    
    # Кнопки управления
    keyboard.row(
        KeyboardButton("🔞 NSFW" if not nsfw_enabled else "🚫 SFW"),
        KeyboardButton("⭐ Избранное")
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

@dp.message_handler(lambda message: message.text.lower() in [g.lower() for g in SFW_GENRES + NSFW_GENRES])
async def send_image(message: types.Message):
    user_id = message.from_user.id
    genre = message.text.lower()
    
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_enabled = cursor.fetchone()[0]
    
    # Проверяем, разрешен ли выбранный жанр в текущем режиме
    available_genres = NSFW_GENRES if nsfw_enabled else SFW_GENRES
    if genre not in available_genres:
        await message.answer("Этот жанр недоступен в текущем режиме")
        return
    
    image_url = await get_image(genre, nsfw_enabled)
    
    if image_url:
        try:
            if image_url.endswith('.gif'):
                await bot.send_animation(message.chat.id, image_url, 
                                       reply_markup=get_keyboard(user_id))
            else:
                await bot.send_photo(message.chat.id, image_url,
                                   reply_markup=get_keyboard(user_id))
        except Exception as e:
            logger.error(f"Send media error: {e}")
            await message.answer("Ошибка отправки изображения")
    else:
        await message.answer("Не удалось загрузить изображение")

@dp.message_handler(lambda message: message.text in ["🔞 NSFW", "🚫 SFW"])
async def toggle_nsfw(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    current = cursor.fetchone()[0]
    
    new_value = not current
    cursor.execute('UPDATE users SET nsfw_enabled = ? WHERE user_id = ?', 
                 (new_value, user_id))
    conn.commit()
    
    await message.answer(f"NSFW режим {'включен' if new_value else 'выключен'}!", 
                       reply_markup=get_keyboard(user_id))

@dp.message_handler(lambda message: message.text == "⭐ Избранное")
async def show_favorites(message: types.Message):
    await message.answer("Функция избранного будет реализована позже", 
                       reply_markup=get_keyboard(message.from_user.id))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
