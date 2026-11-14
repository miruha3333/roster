import time
import requests
from datetime import datetime
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from database import init_db, generate_hash, is_already_published, mark_as_published
from templates import build_telegram_post, filter_unique_trades
from scraper import fetch_player_news

def send_telegram_message(text: str, retries: int = 3) -> bool:
    """Отправляет готовый пост в Telegram с 3 попытками при сбое сети"""
    if not text:
        return False

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("[!] Не задан TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID!")
        return False
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=payload, timeout=15)
            if resp.status_code == 200:
                return True
            print(f"[!] Telegram вернул статус {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"[!] Попытка {attempt}/{retries}: сбой связи с Telegram ({e})")
            time.sleep(2)  # Пауза перед повторной попыткой
            
    return False

def main():
    print("[*] Инициализация базы данных...")
    init_db()

    print("[*] Сканирование DailyFaceoff...")
    raw_news = fetch_player_news()
    
    # Фильтруем дубликаты мега-обменов
    news_list = filter_unique_trades(raw_news)
    print(f"[*] Найдено новостей на странице: {len(news_list)}")

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Разворачиваем: старые первыми, свежие последними
    for item in reversed(news_list):
        if item.get("category") in ["Goalie Start", "Line Change"]:
            n_hash = generate_hash(item["player"], item["category"], today_str)
        else:
            n_hash = generate_hash(item["player"], item["team"], item["text"])

        # Проверка по базе данных
        if is_already_published(n_hash):
            continue

        # Создание публикации
        post_text = build_telegram_post(
            player=item["player"],
            pos_en=item["position"],
            team=item["team"],
            category=item["category"],
            text=item["text"],
            source=item["source"]
        )

        # Пропускаем, если шаблон вернул None
        if not post_text:
            print(f"[-] Пропущено (не подошло под формат): {item['player']} ({item['category']})")
            continue

        # Публикуем
        print(f"[+] Публикация новости: {item['player']} ({item['category']})")
        success = send_telegram_message(post_text)

        if success:
            mark_as_published(n_hash, item["player"], item["category"])
            time.sleep(2)  # Защита от лимитов Telegram
        else:
            print(f"[!] Не удалось опубликовать: {item['player']}")

if __name__ == "__main__":
    main()
