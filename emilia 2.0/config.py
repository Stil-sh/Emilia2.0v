# Правильный формат (используйте ОДИНАРНЫЕ кавычки для значения)
BOT_TOKEN = "7954452949:AAFPjobmKF43QWu6oFC2szX_xTvoc9uClkk"
CHANNEL_ID = "@Emilia_debag"  # Или числовой ID канала
CHANNEL_LINK = "https://t.me/Emilia_debag"
# Или так (можно и двойные, но без дублирования)
# BOT_TOKEN = '7954452949:AAFPjobmKF43QWu6oFC2szX_xTvoc9uClkk'

# Настройки PostgreSQL для Railway
DB_CONFIG = {
    "user": "postgres",
    "password": "MNwCUAjoGdUWxFFdTKIRvqSshcFQOMJO",
    "database": "railway",
    "host": "postgres.railway.internal",
    "port": "5432"  # Укажите ваш порт из настроек Railway
}

BOT_TOKEN = "ВАШ_ТОКЕН"
CHANNEL_ID = "@ВАШ_КАНАЛ"  # Или числовой ID
CHANNEL_LINK = "https://t.me/ВАШ_КАНАЛ"

# Настройки Scrolller API
SCROLLLER_API = "https://api.scrolller.com/api/v2/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

# Категории контента
CATEGORIES = {
    "sfw": {
        "name": "🔒 Безопасный контент",
        "subreddits": ["awwnime", "animewallpaper", "moescape"],
        "nsfw": False
    },
    "nsfw": {
        "name": "🔞 Взрослый контент",
        "subreddits": ["animelegs", "animearmpits", "animelegwear"],
        "nsfw": True
    }
}
