import os
import sqlite3
import requests
from bs4 import BeautifulSoup
import hashlib
import re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "sent_news.db")
URL = "https://www.dailyfaceoff.com/hockey-player-news"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_hash TEXT UNIQUE
        )
    ''')
    conn.commit()
    conn.close()

def get_latest_stored_hash():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    # Берем самый последний добавленный хэш из базы
    cursor.execute('SELECT post_hash FROM sent_posts ORDER BY id DESC LIMIT 1')
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def check_for_new_data():
    init_db()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print("[Watcher] Быстрая проверка ленты...")
    try:
        response = requests.get(URL, headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"[Watcher] Ошибка сайта: {response.status_code}")
            return False
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    
    if not articles:
        return False

    # Берем самый верхний пост на сайте
    top_article = articles[0]
    raw_text = top_article.get_text(separator=" ", strip=True)

    if not raw_text or len(raw_text) < 15:
        return False

    # Убираем динамические таймстампы
    clean_text = re.sub(r'\b(\d+\s*(m|h|d|min|hr|hour|ago|мин|час|д назад))\b', '', raw_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    current_top_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    last_stored_hash = get_latest_stored_hash()

    print(f"[Watcher] Текущий хэш верхушки сайта: {current_top_hash[:8]}")
    print(f"[Watcher] Последний сохраненный в базе хэш: {last_stored_hash[:8] if last_stored_hash else 'Отсутствует'}")

    # Если хэш изменился по сравнению с тем, что в базе — значит, сверху появилась новая запись!
    if current_top_hash != last_stored_hash:
        print("[Watcher] Обнаружено изменение! Верхушка ленты отличается от базы.")
        return True

    print("[Watcher] Верхушка ленты не изменилась. Новостей нет.")
    return False

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    github_output = os.getenv('GITHUB_OUTPUT')
    
    if found_new:
        if github_output:
            with open(github_output, "a") as f:
                f.write("new_news=true\n")
    else:
        if github_output:
            with open(github_output, "a") as f:
                f.write("new_news=false\n")
