import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID

# Настройка логов
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Список жанров (NSFW включены)
GENRES = ["neko", "waifu", "kitsune", "ahegao", "maid"]
NSFW_GENRES = ["ahegao", "hentai", "ass"]  # Доп. NSFW-жанры

# Клавиатура с жанрами
def get_keyboard(nsfw_enabled=False):
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Основные жанры
    for genre in GENRES:
        keyboard.insert(InlineKeyboardButton(genre.capitalize(), callback_data=f"genre_{genre}"))
    
    # NSFW-жанры (если режим включён)
    if nsfw_enabled:
        for genre in NSFW_GENRES:
            keyboard.insert(InlineKeyboardButton(f"🔞 {genre}", callback_data=f"genre_{genre}"))
    
    # Управление
    keyboard.row(
        InlineKeyboardButton("⭐ Избранное", callback_data="favorites"),
        InlineKeyboardButton("🔞 NSFW: ON" if nsfw_enabled else "NSFW: OFF", 
                          callback_data="toggle_nsfw")
    )
    return keyboard

# Получение арта
async def get_art(genre):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://nekos.best/api/v2/{genre}") as response:
                data = await response.json()
                return data["results"][0]["url"]
    except:
        return None

# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer(
        "🎌 Выбери жанр арта (кнопки ниже):",
        reply_markup=get_keyboard()
    )

# Обработка жанров
@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_art(call: types.CallbackQuery):
    genre = call.data.split('_')[1]
    art_url = await get_art(genre)
    
    if art_url:
        await bot.send_photo(call.from_user.id, art_url, 
                           reply_markup=get_keyboard())
    else:
        await call.answer("🚫 Ошибка загрузки. Попробуйте другой жанр.", show_alert=True)

# Переключение NSFW
@dp.callback_query_handler(lambda call: call.data == "toggle_nsfw")
async def toggle_nsfw(call: types.CallbackQuery):
    current_text = call.message.reply_markup.inline_keyboard[-1][1].text
    nsfw_enabled = "ON" in current_text
    
    await call.message.edit_reply_markup(
        reply_markup=get_keyboard(not nsfw_enabled)
    )
    await call.answer(f"NSFW режим {'включён' if not nsfw_enabled else 'выключен'}!")

# Запуск
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
