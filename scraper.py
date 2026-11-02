import re
import requests
from bs4 import BeautifulSoup
from config import DAILYFACEOFF_URL, USER_AGENT

KNOWN_TEAMS = [
    "Anaheim Ducks", "Boston Bruins", "Buffalo Sabres", "Calgary Flames",
    "Carolina Hurricanes", "Chicago Blackhawks", "Colorado Avalanche",
    "Columbus Blue Jackets", "Dallas Stars", "Detroit Red Wings",
    "Edmonton Oilers", "Florida Panthers", "Los Angeles Kings",
    "Minnesota Wild", "Montreal Canadiens", "Nashville Predators",
    "New Jersey Devils", "New York Islanders", "New York Rangers",
    "Ottawa Senators", "Philadelphia Flyers", "Pittsburgh Penguins",
    "San Jose Sharks", "Seattle Kraken", "St Louis Blues", "St. Louis Blues",
    "Tampa Bay Lightning", "Toronto Maple Leafs", "Utah Mammoth", "Utah Hockey Club",
    "Vancouver Canucks", "Vegas Golden Knights", "Washington Capitals",
    "Winnipeg Jets", "Free Agent"
]

def fetch_player_news() -> list[dict]:
    """Скрейпит свежие новости с DailyFaceoff с точным поиском блоков article"""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.dailyfaceoff.com/",
    }

    try:
        response = requests.get(DAILYFACEOFF_URL, headers=headers, timeout=15)
        print(f"[*] Статус ответа сайта: {response.status_code}")
        if response.status_code != 200:
            print(f"[!] Сайт вернул ошибку: {response.status_code}")
            return []
    except Exception as e:
        print(f"[!] Ошибка подключения к сайту: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    
    # 1. Точный поиск указанного вами блока
    articles = soup.find_all(
        "article",
        class_=lambda c: c and "border-gray-200" in c and "flex-col" in c
    )

    # Если класс немного изменился — ищем любые теги <article>
    if not articles:
        articles = soup.find_all("article")

    print(f"[*] Найдено блоков <article> на странице: {len(articles)}")

    news_items = []

    for art in articles:
        text_content = art.get_text(separator="\n").strip()
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]

        if not lines:
            continue

        # --- А. ИЩЕМ ИГРОКА И ПОЗИЦИЮ ---
        # Ищем совпадение шаблона вида: "Matty Beniers(Center)" или "Pavel Mintyukov (Defenseman)"
        player_match = re.search(
            r"([A-Z][a-zA-Z\.\'\-\s]+?)\s*\((Defenseman|Forward|Center|Left Wing|Right Wing|Goalie)[^\)]*\)",
            text_content
        )
        if not player_match:
            continue

        player_name = player_match.group(1).strip()
        position = player_match.group(2).strip()

        # --- Б. ИЩЕМ КОМАНДУ ---
        team = "NHL"
        # Способ 1: по списку известных команд
        for t in KNOWN_TEAMS:
            if t in text_content:
                team = t
                break
        
        # Способ 2: по вертикальной черте "| Team Name"
        if team == "NHL":
            team_pipe_match = re.search(r"\|\s*([A-Za-z0-9\s\.\-]+)", text_content)
            if team_pipe_match:
                candidate = team_pipe_match.group(1).strip().split("\n")[0]
                if candidate:
                    team = candidate

        # --- В. ИЩЕМ КАТЕГОРИЮ ---
        # Категории DailyFaceoff
        cat_match = re.search(
            r"\b(Signing|Trade|Trades|Injury|Line Change|Call Up|Send Down|Roster Moves|Waiver Move|Goalie Start)\b",
            text_content,
            re.IGNORECASE
        )
        category = "News"
        if cat_match:
            raw_cat = cat_match.group(1).title()
            if raw_cat == "Trades":
                category = "Trade"
            elif raw_cat == "Roster Moves":
                category = "Call Up" if "recalled" in text_content.lower() else "Send Down"
            else:
                category = raw_cat

        # --- Г. ИЩЕМ ИСТОЧНИК (SOURCE) ---
        source = ""
        source_match = re.search(r"Source:\s*([^\n]+)", text_content, re.IGNORECASE)
        if source_match:
            source = source_match.group(1).strip()

        # --- Д. ИЩЕМ ОСНОВНОЙ ТЕКСТ НОВОСТИ ---
        # 1-й приоритет: текст из абзацев <p> внутри карточки
        p_tags = art.find_all("p")
        desc_candidates = [
            p.get_text().strip() for p in p_tags 
            if p.get_text().strip() and not p.get_text().strip().startswith("Source:")
        ]

        if desc_candidates:
            news_text = " ".join(desc_candidates)
        else:
            # 2-й приоритет: отсеиваем технические строки и берем смысловой текст
            desc_lines = []
            for line in lines:
                if "Source:" in line or line.startswith("@"):
                    break
                if (line != player_name and 
                    line != category and 
                    line != team and 
                    line != "|" and 
                    not line.startswith(f"{player_name}(")):
                    desc_lines.append(line)
            news_text = " ".join(desc_lines)

        news_text = news_text.strip()
        if not news_text:
            continue

        news_items.append({
            "player": player_name,
            "position": position,
            "team": team,
            "category": category,
            "text": news_text,
            "source": source
        })

    return news_items
