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

def is_post_sent_raw(text_snippet):
    """Проверяет, содержится ли фрагмент новости хоть в одной записи базы"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT post_hash FROM sent_posts')
    rows = cursor.fetchall()
    conn.close()

    # Чистим текст от пробелов и спецсимволов для точного сравнения
    clean_snippet = "".join(e for e in text_snippet if e.isalnum()).lower()

    for row in rows:
        clean_db_row = "".join(e for e in row[0] if e.isalnum()).lower()
        # Если хотя бы часть новости уже есть в базе — значит новость старая
        if clean_snippet in clean_db_row or clean_db_row in clean_snippet:
            return True
    return False

def check_for_new_data():
    init_db()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print("[Watcher] Быстрая проверка страницы...")
    try:
        response = requests.get(URL, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[Watcher] Ошибка загрузки страницы: {response.status_code}")
            return True # На всякий случай запускаем парсер при ошибке
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return True

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    print(f"[Watcher] Найдено блоков <article>: {len(articles)}")

    if not articles:
        print("[Watcher] Блоки не найдены, передаем управление pars.py")
        return True

    # Проверяем первые 3 самые свежие новости
    for article in articles[:3]:
        full_text = article.get_text(separator=" ", strip=True)
        
        if not full_text or len(full_text) < 30 or "fantasy" in full_text.lower():
            continue

        # Возьмем первые 60 символов текста новости
        snippet = full_text[:60]

        # Если хотя бы ОДНОЙ из свежих новостей нет в базе — есть новый контент!
        if not is_post_sent_raw(snippet):
            print(f"[Watcher] НАЙДЕНА НОВАЯ ИНФОРМАЦИЯ: '{snippet[:30]}...'")
            return True

    return False

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    if found_new:
        print("[Watcher] Запуск основного парсера pars.py...")
        result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "pars.py")])
        sys.exit(result.returncode)
    else:
        print("[Watcher] Новой информации нет. Завершение работы (~2 сек).")
        sys.exit(0)
