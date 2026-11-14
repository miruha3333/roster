import os
import sys
from scraper import fetch_player_news
from database import init_db, generate_hash, is_already_published
from datetime import datetime

def check_for_new_data() -> bool:
    """
    Проверяет, есть ли на DailyFaceoff хоть одна новость,
    которой еще нет в нашей реальной базе данных.
    """
    init_db()
    
    print("[Watcher] Сканирование ленты DailyFaceoff...")
    try:
        news_list = fetch_player_news()
    except Exception as e:
        print(f"[Watcher] Ошибка при скачивании новостей: {e}")
        # При ошибке возвращаем True, чтобы подстраховаться и запустить основной скрипт
        return True

    if not news_list:
        print("[Watcher] На странице нет новостей.")
        return False

    today_str = datetime.now().strftime("%Y-%m-%d")

    # Проверяем новости по нашей актуальной базе данных
    for item in news_list:
        if item.get("category") in ["Goalie Start", "Line Change"]:
            n_hash = generate_hash(item["player"], item["category"], today_str)
        else:
            n_hash = generate_hash(item["player"], item["team"], item["text"])

        # Если нашли хотя бы одну новость, которой нет в базе:
        if not is_already_published(n_hash):
            print(f"[Watcher] Найдена свежая новость: {item['player']} ({item.get('category')})")
            return True

    print("[Watcher] Все новости уже есть в базе данных. Обновлений нет.")
    return False

if __name__ == "__main__":
    has_news = check_for_new_data()

    # 1. Если запускается внутри GitHub Actions:
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            f.write(f"new_news={'true' if has_news else 'false'}\n")

    # 2. Если запускается через cron на сервере/компьютере:
    # При наличии новостей напрямую запускаем main.py
    if has_news:
        print("[Watcher] Запуск main.py...")
        from main import main as run_main
        run_main()
