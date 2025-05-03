import logging
import aiohttp
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, ADMIN_ID

# Настройка логов
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Список жанров (можно расширить)
GENRES = ["neko", "waifu", "kitsune", "smug", "maid"]

# Клавиатура с жанрами
def get_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    for genre in GENRES:
        keyboard.add(InlineKeyboardButton(genre.capitalize(), callback_data=f"genre_{genre}"))
    keyboard.add(InlineKeyboardButton("⭐ Избранное", callback_data="favorites"))
    keyboard.add(InlineKeyboardButton("🔞 NSFW Режим", callback_data="nsfw_toggle"))
    keyboard.add(InlineKeyboardButton("📝 Поддержка", callback_data="support"))
    return keyboard

# Получение арта с Nekos.best
async def get_art(genre):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://nekos.best/api/v2/{genre}") as response:
            data = await response.json()
            return data["results"][0]["url"]

# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("🎌 Привет! Я аниме-бот. Выбери жанр:", reply_markup=get_keyboard())

# Обработка кнопок
@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_art(call: types.CallbackQuery):
    genre = call.data.split('_')[1]
    art_url = await get_art(genre)
    await bot.send_photo(call.from_user.id, art_url, reply_markup=get_keyboard())

# Кнопка "Поддержка"
@dp.callback_query_handler(lambda call: call.data == "support")
async def support(call: types.CallbackQuery):
    await call.message.answer("📩 Связь с админом: @ваш_ник")

# Включение NSFW-режима (заглушка)
@dp.callback_query_handler(lambda call: call.data == "nsfw_toggle")
async def toggle_nsfw(call: types.CallbackQuery):
    await call.answer("⚠️ Режим NSFW временно недоступен", show_alert=True)

# Админ-панель
@dp.message_handler(commands=['admincod'])
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🔧 Админ-панель:\n"
                           "/stats - статистика\n"
                           "/add_genre - добавить жанр")

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
