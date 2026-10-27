import os
import re
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# Динамическое определение директории (работает и локально, и на GitHub)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(SCRIPT_DIR, "formatted_news.txt")

# НАСТРОЙКИ TELEGRAM (из секретов GitHub Actions)
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

def translate_status(text_lower, full_text):
    if "upper-body" in text_lower or "upper body" in text_lower:
        return "травма (верхняя часть тела)"
    elif "lower-body" in text_lower or "lower body" in text_lower:
        return "травма (нижняя часть тела)"
    elif "concussion" in text_lower or "protocol" in text_lower:
        return "сотрясение"
    elif "illness" in text_lower:
        return "болезнь"
    elif "hand" in text_lower and "fracture" in text_lower:
        return "перелом руки"
    elif "shoulder" in text_lower:
        return "травма плеча"
    elif "placed on ir" in text_lower:
        return "помещен в список травмированных (IR)"
    elif "surgery" in text_lower or "appendectomy" in text_lower:
        return "перенес операцию"
    elif "reassigned to" in text_lower or "assigned to" in text_lower:
        return "отправлен в фарм-клуб"
    elif "loaned to" in text_lower:
        return "отдан в аренду в фарм-клуб"
    elif "recalled" in text_lower:
        return "вызван из фарм-клуба"
    elif "healthy scratch" in text_lower:
        return "останется в запасе"
    elif "returned to practice" in text_lower or "returns to practice" in text_lower or "was at practice" in text_lower or "practiced" in text_lower:
        return "вернулся к тренировкам"
    elif "will be back" in text_lower or "return to the lineup" in text_lower or "draw back into the lineup" in text_lower or "expected to return" in text_lower:
        return "вернется в состав"
    elif "game-time decision" in text_lower:
        return "решение перед матчем"
    elif "will not play" in text_lower or "out" in text_lower:
        return "пропустит матч"
    elif "warmups" in text_lower or "led the" in text_lower or "skate" in text_lower:
        return "участвует в разминке / готовится к матчу"
    elif "day-to-day" in text_lower:
        return "день за днем (day-to-day)"
    elif "week-to-week" in text_lower:
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
    print("      ПАРСЕР С АВТОМАТИЧЕСКОЙ ОТПРАВКОЙ В TELEGRAM                            ")
    print("================================================================================")

    os.makedirs(SCRIPT_DIR, exist_ok=True)
    new_posts = []

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

    count = 0
    for article in articles:
        if count >= 10:
            break

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
        formatted_post = f"<b>{player_name}</b> {team_eng} {pos_abbr} <b>{status_reason}</b>"

        if formatted_post not in new_posts:
            new_posts.append(formatted_post)
            send_to_telegram(formatted_post)
            count += 1

    print(f"\n[Успех] Обработано и отправлено постов: {len(new_posts)}")

if __name__ == "__main__":
    parse_daily_faceoff()
