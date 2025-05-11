BOT_TOKEN = "7954452949:AAFPjobmKF43QWu6oFC2szX_xTvoc9uClkk"
CHANNEL_ID = "@Emilia_debag"
CHANNEL_LINK = "https://t.me/Emilia_debag"

USER_CATEGORIES = {
    "Безопасный контент 🔒": {
        "Подкатегории": {
            "Геншин Импакт 🌸": ["GenshinImpact"],
            "Хонкай: Звёздный путь 🚂": ["HonkaiStarRail"],
            "Ре:Зеро ⏳": ["Re_Zero"],
            "Неко-девушки 🐾": ["awwnime", "neko"],
            "Аниме-обои 🖼️": ["AnimeWallpaper"]
        },
        "nsfw": False
    },
    "Взрослый контент 🔞": {
        "Подкатегории": {
            "Лоликон 🍭": ["lolicon"],
            "Юри 🌸": ["yuri"],
            "Трапы 🎎": ["traphentai"],
            "Яой 🌈": ["yaoi"],
            "Эротические арты 🍑": ["ecchi", "AnimeBooty"]
        },
        "nsfw": True
    }
}

SCROLLLER_MAPPING = {
    # SFW
    "GenshinImpact": "Genshin_Impact",
    "HonkaiStarRail": "HonkaiStarRail",
    "Re_Zero": "Re_Zero",
    "neko": "neko",
    "AnimeWallpaper": "AnimeWallpaper",
    
    # NSFW
    "lolicon": "loliconnsfw",
    "yuri": "yuri",
    "traphentai": "traphentai",
    "yaoi": "yaoi",
    "ecchi": "ecchi",
    "AnimeBooty": "AnimeBooty"
}
