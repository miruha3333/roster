import os
import sqlite3
import sys
import subprocess
import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(SCRIPT_DIR, "sent_news.db")
URL = "https://www.dailyfaceoff.com/hockey-player-news"

POSITIONS_MAP = {
    "center": "C",
    "left wing": "LW",
    "right wing": "RW",
    "defenseman": "D",
    "goalie": "G"
}

NHL_TEAMS = [
    "Anaheim Ducks", "Boston Bruins", "Buffalo Sabres", "Calgary Flames", "Carolina Hurricanes",
    "Chicago Blackhawks", "Colorado Avalanche", "Columbus Blue Jackets", "Dallas Stars", "Detroit Red Wings",
    "Edmonton Oilers", "Florida Panthers", "Los Angeles Kings", "Minnesota Wild", "Montreal Canadiens",
    "Nashville Predators", "New Jersey Devils", "New York Islanders", "New York Rangers", "Ottawa Senators",
    "Philadelphia Flyers", "Pittsburgh Penguins", "San Jose Sharks", "Seattle Kraken", "St. Louis Blues",
    "Tampa Bay Lightning", "Toronto Maple Leafs", "Utah Hockey Club", "Vancouver Canucks", "Vegas Golden Knights",
    "Washington Capitals", "Winnipeg Jets"
]

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

def translate_status(text_lower):
    if "upper-body" in text_lower or "upper body" in text_lower:
        return "травма (верхняя часть тела)"
    elif "lower-body" in text_lower or "lower body" in text_lower:
        return "травма (нижняя часть тела)"
    elif "concussion" in text_lower or "protocol" in text_lower:
        return "сотрясение"
    elif "illness" in text_lower:
        return "болезнь"
    elif "placed on ir" in text_lower:
        return "помещен в список травмированных (IR)"
    elif "surgery" in text_lower:
        return "перенес операцию"
    elif "reassigned to" in text_lower or "assigned to" in text_lower:
        return "отправлен в фарм-клуб"
    elif "recalled" in text_lower:
        return "вызван из фарм-клуба"
    elif "returned to practice" in text_lower or "practiced" in text_lower:
        return "вернулся к тренировкам"
    elif "will not play" in text_lower or "out" in text_lower:
        return "пропустит матч"
    elif "day-to-day" in text_lower:
        return "день за днем (day-to-day)"
    return "изменение статуса"

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
            return False
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return False

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    print(f"[Watcher] Найдено блоков <article>: {len(articles)}")

    for article in articles[:5]:
        full_text = article.get_text(separator=" ", strip=True)
        text_lower = full_text.lower()

        if not full_text or len(full_text) < 30 or "fantasy" in text_lower:
            continue

        pos_abbr = None
        for p_eng, p_short in POSITIONS_MAP.items():
            if p_eng in text_lower:
                pos_abbr = f"({p_short})"
                break

        if not pos_abbr:
            continue

        # Быстрый поиск кандидатов для имени
        links = article.find_all(['a', 'h2', 'h3', 'span'])
        valid_candidates = []
        for el in links:
            t = el.get_text(strip=True)
            if len(t) > 2 and t not in valid_candidates and not t.isdigit():
                if not any(w in t.lower() for w in ["injury", "source", "ago", "oct", "nov", "dec", "jan", "feb", "mar", "apr", "2026", "news", "updates"]):
                    if len(t) < 35:
                        valid_candidates.append(t)

        player_name = ""
        team_eng = ""

        for cand in valid_candidates:
            matched_team = None
            for t in NHL_TEAMS:
                if t.lower() == cand.lower() or t.lower() in cand.lower():
                    matched_team = t
                    break
            if matched_team:
                team_eng = matched_team
            elif not player_name and len(cand.split()) >= 2:
                player_name = cand

        if not player_name or not team_eng:
            continue

        status_reason = translate_status(text_lower)
        post_unique_id = f"{player_name}_{team_eng}_{pos_abbr}_{status_reason}".lower()

        # Проверяем точно такой же хэш, какой использует pars.py
        if not is_post_sent(post_unique_id):
            print(f"[Watcher] НАЙДЕНА НОВАЯ ИНФОРМАЦИЯ для {player_name}! Запускаем тяжелый парсер...")
            return True

    return False

if __name__ == "__main__":
    found_new = check_for_new_data()
    
    if found_new:
        print("[Watcher] Запуск pars.py...")
        result = subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "pars.py")])
        sys.exit(result.returncode)
    else:
        print("[Watcher] Новой информации нет. Завершение работы (~2 сек).")
        sys.exit(0)
