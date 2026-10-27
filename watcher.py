import os
import sqlite3
import sys
import subprocess
import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "sent_news.db")
URL = "https://www.dailyfaceoff.com/hockey-player-news"

POSITIONS = ["center", "left wing", "right wing", "defenseman", "goalie"]

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

def is_post_sent(post_hash):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sent_posts WHERE post_hash = ?', (post_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def check_for_new_data():
    """Быстрая проверка без Playwright (занимает 2 секунды)"""
    init_db()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print("[Watcher] Быстрая проверка страницы...")
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[Watcher] Ошибка загрузки страницы: {response.status_code}")
            return False
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    print(f"[Watcher] Найдено блоков <article>: {len(articles)}")

    has_new_info = False

    for article in articles[:5]:  # Смотрим только первые 5 самых свежих новостей
        full_text = article.get_text(separator=" ", strip=True)
        text_lower = full_text.lower()

        if not full_text or len(full_text) < 30 or "fantasy" in text_lower:
            continue

        # Быстро вытаскиваем имя и амплуа
        has_pos = any(pos in text_lower for pos in POSITIONS)
        if not has_pos:
            continue

        # Создаем первичный хэш из текста карточки
        # Берем первые 80 символов текста новости для сверки с базой
        short_hash_key = re_clean(full_text[:100]).lower()

        if not is_post_sent_by_keyword(short_hash_key):
            print(f"[Watcher] НАЙДЕНА НОВАЯ ИНФОРМАЦИЯ! Запускаем тяжелый парсер...")
            has_new_info = True
            break

    return has_new_info

def is_post_sent_by_keyword(keyword_part):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT post_hash FROM sent_posts')
    rows = cursor.fetchall()
    conn.close()
    for row in rows:
        if keyword_part in row[0]:
            return True
    return False

def re_clean(text):
    import re
    return re.sub(r'[^a-zA-Z0-9]', '', text)

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    if found_new:
        # Запускаем основной тяжелый парсер
        print("[Watcher] Запуск pars.py...")
        result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "pars.py")])
        sys.exit(result.returncode)
    else:
        print("[Watcher] Новой информации нет. Завершение работы (заняло ~2 сек).")
        sys.exit(0)
