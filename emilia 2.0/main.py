import logging
from aiogram import Bot, Dispatcher, types, executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN
import aiohttp

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# Жанры из Waifu.pics
GENRES = {
    "waifu": "Девушки",
    "neko": "Неко",
    "shinobu": "Шинобу",
    "megumin": "Мегумин",
    "bully": "Буллинг",
    "cuddle": "Обнимашки",
    "awoo": "Волки"
}

# Клавиатура
def get_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    for genre, label in GENRES.items():
        keyboard.insert(InlineKeyboardButton(label, callback_data=f"genre_{genre}"))
    keyboard.add(InlineKeyboardButton("⭐ Избранное", callback_data="favorites"))
    return keyboard

# Получение арта с Waifu.pics
async def get_waifu_image(genre):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.waifu.pics/sfw/{genre}") as resp:
            data = await resp.json()
            return data["url"]

# Обработчик кнопок
@dp.callback_query_handler(lambda call: call.data.startswith('genre_'))
async def send_waifu(call: types.CallbackQuery):
    genre = call.data.split('_')[1]
    try:
        image_url = await get_waifu_image(genre)
        await bot.send_photo(call.from_user.id, image_url, reply_markup=get_keyboard())
    except Exception as e:
        await call.answer(f"Ошибка: {e}", show_alert=True)

@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Выбери жанр аниме-арта:", reply_markup=get_keyboard())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
