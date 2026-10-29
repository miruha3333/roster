import os
import sqlite3
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

def translate_status(text_lower):
    # Точно такой же словарь статусов, как в pars.py
    if "will start" in text_lower or "in the starter's crease" in text_lower or "starter's crease" in text_lower:
        return "стартовый голкипер"
    elif "upper-body injury" in text_lower or "upper body injury" in text_lower:
        return "травма верхней части тела"
    elif "lower-body injury" in text_lower or "lower body injury" in text_lower:
        return "травма нижней части тела"
    elif "concussion protocol" in text_lower:
        return "протокол сотрясения мозга"
    elif "miss time with an illness" in text_lower or "out with an illness" in text_lower:
        return "пропустит матч из-за болезни"
    elif "hand fracture" in text_lower or "fractured hand" in text_lower:
        return "перелом руки"
    elif "shoulder injury" in text_lower:
        return "травма плеча"
    elif "placed on injured reserve" in text_lower or "placed on ir" in text_lower:
        return "помещен в список травмированных (IR)"
    elif "underwent surgery" in text_lower or "had surgery" in text_lower:
        return "перенес операцию"
    elif "reassigned to the AHL" in text_lower or "assigned to the AHL" in text_lower:
        return "отправлен в АХЛ"
    elif "loaned to" in text_lower:
        return "отдан в аренду"
    elif "recalled from the AHL" in text_lower or "recalled from ahl" in text_lower:
        return "вызван из АХЛ"
    elif "will be a healthy scratch" in text_lower or "healthy scratch" in text_lower:
        return "останется в запасе (healthy scratch)"
    elif "returned to practice" in text_lower or "returns to practice" in text_lower:
        return "вернулся к тренировкам"
    elif "expected to return to the lineup" in text_lower or "return to the lineup" in text_lower:
        return "вернется в состав"
    elif "game-time decision" in text_lower:
        return "решение по участию будет принято перед матчем"
    elif "will not play" in text_lower or "ruled out for" in text_lower:
        return "пропустит матч"
    elif "considered day-to-day" in text_lower or "listed as day-to-day" in text_lower:
        return "день за днем (day-to-day)"
    elif "considered week-to-week" in text_lower or "listed as week-to-week" in text_lower:
        return "неделя за неделей (week-to-week)"
    return "изменение статуса"

def is_post_sent(post_hash):
    if not os.path.exists(DB_FILE):
        return False
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM sent_posts WHERE post_hash = ?', (post_hash,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def check_for_new_data():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    print("[Watcher] Быстрая проверка ленты через requests...")
    try:
        response = requests.get(URL, headers=headers, timeout=5)
        if response.status_code != 200:
            print(f"[Watcher] Ошибка сайта: {response.status_code}")
            return True # При сбое лучше подстраховаться и запустить парсер
    except Exception as e:
        print(f"[Watcher] Ошибка запроса: {e}")
        return True

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    
    if not articles:
        return False

    # Берем самый первый (самый свежий) пост и парсим его точно так же, как pars.py
    top_article = articles[0]
    full_text = top_article.get_text(separator=" ", strip=True)
    text_lower = full_text.lower()

    if not full_text or "fantasy" in text_lower or "betting" in text_lower or len(full_text) < 30:
        return False

    pos_abbr = None
    for p_eng, p_short in POSITIONS_MAP.items():
        if p_eng in text_lower:
            pos_abbr = f"({p_short})"
            break

    if not pos_abbr:
        return False

    links = top_article.find_all(['a', 'h2', 'h3', 'span'])
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
        return False

    status_reason = translate_status(text_lower)
    
    # Формируем ТОТ ЖЕ САМЫЙ уникальный ключ, который проверяет pars.py
    top_post_unique_id = f"{player_name}_{team_eng}_{pos_abbr}_{status_reason}".lower()

    print(f"[Watcher] Топовый пост: {player_name} ({team_eng}) -> {status_reason}")

    # Проверяем по общей базе данных
    if not is_post_sent(top_post_unique_id):
        print("[Watcher] Данного поста еще нет в базе! Есть реальные изменения.")
        return True

    print("[Watcher] Верхний пост уже есть в базе. Изменений нет.")
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
