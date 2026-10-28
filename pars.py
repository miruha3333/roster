import os
import re
import sqlite3
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Динамическое определение пути к файлам
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "formatted_news.txt")
DB_FILE = os.path.join(SCRIPT_DIR, "sent_news.db")

# Чтение секретов
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")

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
    """Создание таблицы в базе данных"""
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
    """Проверка наличия поста в базе"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sent_posts WHERE post_hash = ?', (post_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_sent_post(post_hash):
    """Сохранение поста в базу"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO sent_posts (post_hash) VALUES (?)', (post_hash,))
        conn.commit()
    except sqlite3.IntegrityError:
        pass
    finally:
        conn.close()

def translate_status(text_lower, full_text=""):
    # Используем полный исходный текст для поиска точных фраз с сохранением регистра (или переведенный в нижний)
    t_lower = text_lower

    # 1. Точные фразы для стартовых вратарей
    if "will start" in t_lower or "in the starter's crease" in t_lower or "starter's crease" in t_lower or "is in the starter's crease" in t_lower:
        return "стартовый голкипер"

    # 2. Точные фразы для травм и медицинских статусов
    elif "upper-body injury" in t_lower or "upper body injury" in t_lower:
        return "травма верхней части тела"
    elif "lower-body injury" in t_lower or "lower body injury" in t_lower:
        return "травма нижней части тела"
    elif "concussion protocol" in t_lower:
        return "протокол сотрясения мозга"
    elif "miss time with an illness" in t_lower or "out with an illness" in t_lower:
        return "пропустит матч из-за болезни"
    elif "hand fracture" in t_lower or "fractured hand" in t_lower:
        return "перелом руки"
    elif "shoulder injury" in t_lower:
        return "травма плеча"
    elif "placed on injured reserve" in t_lower or "placed on ir" in t_lower:
        return "помещен в список травмированных (IR)"
    elif "underwent surgery" in t_lower or "had surgery" in t_lower:
        return "перенес операцию"

    # 3. Фразы про бедро и сроки восстановления (как в вашем примере с Ducks)
    elif "is hopeful to join" in t_lower and "workouts" in t_lower:
        return "надеется вернуться к тренировкам в ближайшее время"
    elif "hip injury" in t_lower or "hip issue" in t_lower:
        return "травма бедра"

    # 4. Неразглашаемые травмы с возможностью сыграть
    elif "undisclosed injury" in t_lower and "option to play" in t_lower:
        return "травма (характер не разглашается), но может сыграть"
    elif "undisclosed injury" in t_lower or "undisclosed issue" in t_lower:
        return "травма (характер не разглашается)"

    # 5. Движение по составу и фарм-клубам
    elif "reassigned to the AHL" in t_lower or "assigned to the AHL" in t_lower:
        return "отправлен в АХЛ"
    elif "loaned to" in t_lower:
        return "отдан в аренду"
    elif "recalled from the AHL" in t_lower or "recalled from ahl" in t_lower:
        return "вызван из АХЛ"
    elif "will be a healthy scratch" in t_lower or "healthy scratch" in t_lower:
        return "останется в запасе (healthy scratch)"

    # 6. Возвращение в строй и тренировки
    elif "returned to practice" in t_lower or "returns to practice" in t_lower:
        return "вернулся к тренировкам"
    elif "expected to return to the lineup" in t_lower or "return to the lineup" in t_lower:
        return "вернется в состав"
    elif "game-time decision" in t_lower:
        return "решение по участию будет принято перед матчем"

    # 7. Пропуск матчей и сроки
    elif "will not play" in t_lower or "ruled out for" in t_lower:
        return "пропустит матч"
    elif "considered day-to-day" in t_lower or "listed as day-to-day" in t_lower:
        return "день за днем (day-to-day)"
    elif "considered week-to-week" in t_lower or "listed as week-to-week" in t_lower:
        return "неделя за неделей (week-to-week)"

    return "изменение статуса"

def send_to_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not CHANNEL_ID:
        print("[Ошибка]: TELEGRAM_BOT_TOKEN или TELEGRAM_CHANNEL_ID не заданы!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"[Ошибка Telegram]: {response.text}")
    except Exception as e:
        print(f"[Ошибка отправки в Telegram]: {e}")

def parse_daily_faceoff():
    print("================================================================================")
    print("      ПАРСЕР С ЗАЩИТОЙ ОТ ДУБЛИКАТОВ ЧЕРЕЗ БД (SQLite)                        ")
    print("================================================================================")

    init_db()
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    new_posts_sent = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        page = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ).new_page()

        print("Загрузка страницы https://www.dailyfaceoff.com/hockey-player-news ...")
        try:
            page.goto("https://www.dailyfaceoff.com/hockey-player-news", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)
            html_content = page.content()
        except Exception as e:
            print(f"[Ошибка загрузки]: {e}")
            browser.close()
            return

        browser.close()

    soup = BeautifulSoup(html_content, 'html.parser')
    articles = soup.find_all('article')
    print(f"Найдено блоков <article>: {len(articles)}")

    for article in articles:
        full_text = article.get_text(separator=" ", strip=True)
        text_lower = full_text.lower()

        if not full_text or "fantasy" in text_lower or "betting" in text_lower or len(full_text) < 30:
            continue

        pos_abbr = None
        for p_eng, p_short in POSITIONS_MAP.items():
            if p_eng in text_lower:
                pos_abbr = f"({p_short})"
                break

        if not pos_abbr:
            continue

        links = article.find_all(['a', 'h2', 'h3', 'span'])
        valid_candidates = []
        for el in links:
            t = el.get_text(strip=True)
            if len(t) > 2 and t not in valid_candidates and not t.isdigit():
                if not any(w in t.lower() for w in ["injury", "source", "ago", "oct", "nov", "dec", "jan", "feb", "mar", "apr", "2026", "news", "updates", "center", "left wing", "right wing", "defenseman", "goalie"]):
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

        if not player_name and len(valid_candidates) >= 1:
            is_first_team = any(t.lower() == valid_candidates[0].lower() for t in NHL_TEAMS)
            if not is_first_team:
                player_name = valid_candidates[0]
            elif len(valid_candidates) >= 2:
                player_name = valid_candidates[1]

        if not team_eng or team_eng == "NHL Team" or team_eng.lower() == player_name.lower():
            for team in NHL_TEAMS:
                if team.lower() in text_lower:
                    team_eng = team
                    break
            if not team_eng:
                team_eng = "NHL Team"

        if not player_name:
            continue

        status_reason = translate_status(text_lower, full_text)
        
        # Уникальный ключ для базы
        post_unique_id = f"{player_name}_{team_eng}_{pos_abbr}_{status_reason}".lower()

        # Если поста нет в базе — отправляем и сохраняем
        if not is_post_sent(post_unique_id):
            formatted_post = f"<b>{player_name}</b> {team_eng} {pos_abbr} <b>{status_reason}</b>"
            send_to_telegram(formatted_post)
            save_sent_post(post_unique_id)
            new_posts_sent += 1
            print(f"[Новый пост]: {player_name} - {status_reason}")

    print(f"\n[Успех] Новых постов отправлено: {new_posts_sent}")

if __name__ == "__main__":
    parse_daily_faceoff()
