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

# Инициализация БД
conn = sqlite3.connect('users.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                  (user_id INTEGER PRIMARY KEY, 
                   nsfw_enabled BOOLEAN DEFAULT FALSE)''')
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
    "trap": "Трап (18+)",
    "blowjob": "БДСМ (18+)"
}

# Клавиатуры
def get_main_keyboard(user_id):
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_status = cursor.fetchone()[0] if cursor.fetchone() else False
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем соответствующие жанры
    genres = NSFW_GENRES if nsfw_status else SFW_GENRES
    for genre, label in genres.items():
        keyboard.insert(InlineKeyboardButton(label, callback_data=f"genre_{genre}"))
    
    # Кнопка переключения режима
    mode_button = InlineKeyboardButton(
        "🔞 Выключить NSFW" if nsfw_status else "🔞 Включить NSFW", 
        callback_data="toggle_nsfw"
    )
    keyboard.add(mode_button)
    keyboard.add(InlineKeyboardButton("📝 Поддержка", url="t.me/username"))
    
    return keyboard

# Получение изображения
async def get_image(genre, nsfw=False):
    category = "nsfw" if nsfw else "sfw"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.waifu.pics/{category}/{genre}") as resp:
                data = await resp.json()
                return data['url']
    except Exception as e:
        logger.error(f"API error: {e}")
        return None

# Обработчики
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
    conn.commit()
    await message.answer("🎌 Выбери жанр:", reply_markup=get_main_keyboard(user_id))

@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_image(call: types.CallbackQuery):
    user_id = call.from_user.id
    genre = call.data.split('_')[1]
    
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_status = cursor.fetchone()[0] if cursor.fetchone() else False
    
    image_url = await get_image(genre, nsfw_status)
    if image_url:
        await bot.send_photo(user_id, image_url, reply_markup=get_main_keyboard(user_id))
    else:
        await call.answer("Ошибка загрузки. Попробуйте позже.", show_alert=True)

@dp.callback_query_handler(lambda call: call.data == 'toggle_nsfw')
async def toggle_nsfw(call: types.CallbackQuery):
    user_id = call.from_user.id
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    current_status = cursor.fetchone()[0] if cursor.fetchone() else False
    
    # Проверка возраста для NSFW
    if not current_status:
        await bot.send_message(
            user_id, 
            "⚠️ Внимание! Контент для взрослых.\n"
            "Подтвердите, что вам есть 18 лет:",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("✅ Мне есть 18", callback_data="confirm_age")
            )
        )
        return
    
    cursor.execute('UPDATE users SET nsfw_enabled = ? WHERE user_id = ?', (not current_status, user_id))
    conn.commit()
    await call.message.edit_reply_markup(get_main_keyboard(user_id))

@dp.callback_query_handler(lambda call: call.data == 'confirm_age')
async def confirm_age(call: types.CallbackQuery):
    user_id = call.from_user.id
    cursor.execute('UPDATE users SET nsfw_enabled = TRUE WHERE user_id = ?', (user_id,))
    conn.commit()
    await call.message.delete()
    await call.message.answer("Режим NSFW активирован!", reply_markup=get_main_keyboard(user_id))

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
