import os
import sqlite3
import sys
import subprocess
import requests
from bs4 import BeautifulSoup

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

def check_for_new_data():
    init_db()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print("[Watcher] Быстрая проверка ленты...")
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[Watcher] Ошибка сайта: {response.status_code}")
            return True # При сбое сайта на всякий случай даем запуск
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return True

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    
    if not articles:
        return True

    # Берем САМУЮ СВЕЖУЮ (первую) новость со страницы
    top_article = articles[0]
    raw_text = top_article.get_text(separator=" ", strip=True)

    if not raw_text or len(raw_text) < 15:
        return False

    # Делаем простой стабильный хэш из текста верхнего поста
    import hashlib
    top_hash = hashlib.md5(raw_text.encode('utf-8')).hexdigest()

    # Сверяем этот хэш с последней записью в базе
    # (Или просто проверяем, есть ли хэш топовой новости в нашей БД)
    if not is_hash_in_db(top_hash):
        print([f"[Watcher] Обнаружена новая свежая запись! (Хэш: {top_hash[:8]})"])
        return True

    return False

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    if found_new:
        print("[Watcher] Запуск основного парсера pars.py...")
        result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "pars.py")])
        sys.exit(result.returncode)
    else:
        print("[Watcher] Новых записей нет. Выход (2 сек).")
        sys.exit(0)
