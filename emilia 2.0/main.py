import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID
import aiohttp
import sqlite3
from time import time

# Настройка логов
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация бота с таймаутом
bot = Bot(token=BOT_TOKEN, timeout=30)  # Увеличили таймаут для API
dp = Dispatcher(bot)

# Инициализация БД с WAL-режимом для лучшей производительности
conn = sqlite3.connect('users.db', check_same_thread=False)
conn.execute('PRAGMA journal_mode=WAL')  # Улучшаем работу с БД
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

# Кэш для хранения клавиатур
keyboard_cache = {}

def get_main_keyboard(user_id):
    # Проверяем кэш
    cache_key = f"keyboard_{user_id}"
    if cache_key in keyboard_cache:
        return keyboard_cache[cache_key]
    
    cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
    nsfw_status = cursor.fetchone()[0] if cursor.fetchone() else False
    
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    genres = NSFW_GENRES if nsfw_status else SFW_GENRES
    for genre, label in genres.items():
        keyboard.insert(InlineKeyboardButton(label, callback_data=f"genre_{genre}"))
    
    mode_button = InlineKeyboardButton(
        "🔞 Выключить NSFW" if nsfw_status else "🔞 Включить NSFW", 
        callback_data="toggle_nsfw"
    )
    keyboard.add(mode_button)
    keyboard.add(InlineKeyboardButton("📝 Поддержка", url="t.me/username"))
    
    # Сохраняем в кэш
    keyboard_cache[cache_key] = keyboard
    return keyboard

# Получение изображения с таймаутом и повторными попытками
async def get_image(genre, nsfw=False, retries=3):
    category = "nsfw" if nsfw else "sfw"
    timeout = aiohttp.ClientTimeout(total=10)  # Таймаут 10 секунд
    
    for attempt in range(retries):
        try:
            start_time = time()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"https://api.waifu.pics/{category}/{genre}") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"Image loaded in {time()-start_time:.2f}s")
                        return data['url']
                    else:
                        logger.warning(f"API status {resp.status}, attempt {attempt+1}")
        except Exception as e:
            logger.warning(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt == retries - 1:
                return None

# Обработчики
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    try:
        cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()
        await message.answer("🎌 Выбери жанр:", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"Start error: {e}")
        await message.answer("Произошла ошибка. Попробуйте позже.")

@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_image(call: types.CallbackQuery):
    user_id = call.from_user.id
    genre = call.data.split('_')[1]
    
    try:
        # Показываем уведомление о загрузке
        await call.answer("Загрузка...", cache_time=5)
        
        cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
        nsfw_status = cursor.fetchone()[0] if cursor.fetchone() else False
        
        image_url = await get_image(genre, nsfw_status)
        if image_url:
            await bot.send_photo(user_id, image_url, reply_markup=get_main_keyboard(user_id))
        else:
            await call.answer("Ошибка загрузки. Попробуйте позже.", show_alert=True)
    except Exception as e:
        logger.error(f"Send image error: {e}")
        await call.answer("Произошла ошибка", show_alert=True)

@dp.callback_query_handler(lambda call: call.data == 'toggle_nsfw')
async def toggle_nsfw(call: types.CallbackQuery):
    user_id = call.from_user.id
    try:
        cursor.execute('SELECT nsfw_enabled FROM users WHERE user_id = ?', (user_id,))
        current_status = cursor.fetchone()[0] if cursor.fetchone() else False
        
        if not current_status:
            # Удаляем старое сообщение с кнопками
            await call.message.delete()
            
            # Отправляем подтверждение
            msg = await bot.send_message(
                user_id,
                "⚠️ Внимание! Контент для взрослых.\n"
                "Подтвердите, что вам есть 18 лет:",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("✅ Мне есть 18", callback_data="confirm_age"),
                    InlineKeyboardButton("❌ Отмена", callback_data="cancel_age")
                )
            )
            return
        
        # Обновляем статус и клавиатуру
        cursor.execute('UPDATE users SET nsfw_enabled = ? WHERE user_id = ?', (not current_status, user_id))
        conn.commit()
        
        # Очищаем кэш для этого пользователя
        cache_key = f"keyboard_{user_id}"
        if cache_key in keyboard_cache:
            del keyboard_cache[cache_key]
            
        await call.message.edit_reply_markup(get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"Toggle NSFW error: {e}")
        await call.answer("Произошла ошибка", show_alert=True)

@dp.callback_query_handler(lambda call: call.data == 'confirm_age')
async def confirm_age(call: types.CallbackQuery):
    try:
        user_id = call.from_user.id
        cursor.execute('UPDATE users SET nsfw_enabled = TRUE WHERE user_id = ?', (user_id,))
        conn.commit()
        
        # Очищаем кэш
        cache_key = f"keyboard_{user_id}"
        if cache_key in keyboard_cache:
            del keyboard_cache[cache_key]
        
        await call.message.delete()
        await call.message.answer("Режим NSFW активирован!", reply_markup=get_main_keyboard(user_id))
    except Exception as e:
        logger.error(f"Confirm age error: {e}")
        await call.answer("Произошла ошибка", show_alert=True)

@dp.callback_query_handler(lambda call: call.data == 'cancel_age')
async def cancel_age(call: types.CallbackQuery):
    try:
        await call.message.delete()
        await call.message.answer("Доступ к NSFW-контенту не предоставлен.", reply_markup=get_main_keyboard(call.from_user.id))
    except Exception as e:
        logger.error(f"Cancel age error: {e}")

if __name__ == '__main__':
    try:
        executor.start_polling(dp, skip_updates=True)
    finally:
        conn.close()  # Закрываем соединение с БД при выходе
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
