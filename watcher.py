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

def is_hash_in_db(post_hash):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sent_posts WHERE post_hash = ?', (post_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_hash_to_db(post_hash):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT OR IGNORE INTO sent_posts (post_hash) VALUES (?)', (post_hash,))
        conn.commit()
    except Exception as e:
        print(f"[Watcher] Ошибка сохранения хэша в БД: {e}")
    finally:
        conn.close()

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

    # Берем самый верхний пост
    top_article = articles[0]
    raw_text = top_article.get_text(separator=" ", strip=True)

    if not raw_text or len(raw_text) < 15:
        return False

    # Убираем динамические таймстампы (минуты/часы назад), оставляя суть новости
    clean_text = re.sub(r'\b(\d+\s*(m|h|d|min|hr|hour|ago|мин|час|д назад))\b', '', raw_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    top_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()

    # Проверяем в базе
    if not is_hash_in_db(top_hash):
        print(f"[Watcher] Обнаружена реально новая запись! (Хэш: {top_hash[:8]})")
        # ВАЖНО: Сразу сохраняем хэш в базу, чтобы больше не триггерить повторно
        save_hash_to_db(top_hash)
        return True

    print("[Watcher] Изменений нет (новость уже обрабатывалась).")
    return False

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    github_output = os.getenv('GITHUB_OUTPUT')
    
    if found_new:
        print("[Watcher] Есть новые данные. Даем сигнал на запуск парсера.")
        if github_output:
            with open(github_output, "a") as f:
                f.write("new_news=true\n")
    else:
        print("[Watcher] Новых записей нет. Завершаем работу за пару секунд.")
        if github_output:
            with open(github_output, "a") as f:
                f.write("new_news=false\n")
