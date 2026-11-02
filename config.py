import os

# Токен бота и ID канала берутся из настроек GitHub Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # Например: @xokkey9

DAILYFACEOFF_URL = "https://www.dailyfaceoff.com/hockey-player-news"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

POSITIONS = {
    "Defenseman": "Защитник",
    "Forward": "Нападающий",
    "Center": "Центрфорвард",
    "Left Wing": "Левый крайний",
    "Right Wing": "Правый крайний",
    "Goalie": "Вратарь"
}

DAYS_TRANSLATE = {
    "Sunday": "в воскресенье", "Monday": "в понедельник", "Tuesday": "во вторник",
    "Wednesday": "в среду", "Thursday": "в четверг", "Friday": "в пятницу",
    "Saturday": "в субботу", "today": "сегодня", "tonight": "сегодня ночью"
}

INJURIES_TRANSLATE = {
    "upper-body": "верхняя часть тела",
    "upper body": "верхняя часть тела",
    "lower-body": "нижняя часть тела",
    "lower body": "нижняя часть тела",
    "undisclosed": "не раскрывается",
    "illness": "болезнь / простуда",
    "knee": "колено",
    "hip": "бедро",
    "groin": "пах",
    "shoulder": "плечо",
    "concussion": "сотрясение мозга",
    "wrist": "запястье"
}
