import time
import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHANNEL_ID
from database import init_db, generate_hash, is_already_published, mark_as_published
from templates import build_telegram_post
from scraper import fetch_player_news

def send_telegram_message(text: str) -> bool:
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
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as e:
        print(f"[!] Сбой отправки в Telegram: {e}")
        return False

def main():
    print("[*] Инициализация базы данных...")
    init_db()

    print("[*] Сканирование DailyFaceoff...")
    news_list = fetch_player_news()
    print(f"[*] Найдено новостей на странице: {len(news_list)}")

    # Разворачиваем, чтобы старые по времени новости шли первыми, а свежие — последними
    for item in reversed(news_list):
        n_hash = generate_hash(item["player"], item["team"], item["text"])

        # Проверка защиты от дубликатов
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

        print(f"[+] Публикация новости: {item['player']} ({item['category']})")
        success = send_telegram_message(post_text)

        if success:
            mark_as_published(n_hash, item["player"], item["category"])
            # Небольшая пауза между постами, чтобы Telegram не блокировал за спам
            time.sleep(2)
        else:
            print(f"[!] Не удалось опубликовать: {item['player']}")

if __name__ == "__main__":
    main()
