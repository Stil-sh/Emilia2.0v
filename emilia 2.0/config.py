BOT_TOKEN = "7954452949:AAFPjobmKF43QWu6oFC2szX_xTvoc9uClkk"
CHANNEL_ID = "@Emilia_debag"
CHANNEL_LINK = "https://t.me/Emilia_debag"

USER_CATEGORIES = {
    "Безопасный контент 🔒": {
        "Подкатегории": {
            "Геншин Импакт 🏮": ["Genshin_Impact"],
            "Хонкай: Звёздный рельс 🌌": ["HonkaiStarRail"],
            "Ре: Зеро ⏳": ["Re_Zero"],
            "Няшки-неко 🐾": ["awwnime", "neko"],
            "Аниме-арты 🎨": ["AnimeART"],
            "Мемы про аниме 🤣": ["Animemes"]
        },
        "nsfw": False
    },
    "Взрослый контент 🔞": {
        "Подкатегории": {
            "Лоликон 👧": ["lolicon"],
            "Юри 🌸": ["yuri"),
            "Неко-эротика 🐾": ["neko_NSFW"],
            "Трапы 🎎": ["traphentai"),
            "Яой 💢": ["yaoi"),
            "Экстремальные арты 🔥": ["HentaiHardcore")
        },
        "nsfw": True
    }
}

SCROLLLER_MAPPING = {
    # SFW
    "Genshin_Impact": "GenshinImpact",
    "HonkaiStarRail": "HonkaiStarRail",
    "Re_Zero": "Re_Zero",
    "awwnime": "awwnime",
    "neko": "neko",
    "AnimeART": "AnimeART",
    "Animemes": "goodanimemes",
    
    # NSFW
    "lolicon": "loliconnsfw",
    "yuri": "yurihentai",
    "neko_NSFW": "nekonsfw",
    "traphentai": "traphentai",
    "yaoi": "yaoi",
    "HentaiHardcore": "HentaiHardcore"
}
