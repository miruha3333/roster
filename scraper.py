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

POSITIONS_MAP = {
    "defenseman": "Defenseman", "defense": "Defenseman", "d": "Defenseman",
    "forward": "Forward", "f": "Forward",
    "center": "Center", "c": "Center",
    "left wing": "Left Wing", "lw": "Left Wing",
    "right wing": "Right Wing", "rw": "Right Wing",
    "goalie": "Goalie", "g": "Goalie"
}

def clean_inline_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def fetch_player_news() -> list[dict]:
    """Универсальный скрейпер карточек DailyFaceoff по DOM-элементам"""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.dailyfaceoff.com/",
    }

    try:
        response = requests.get(DAILYFACEOFF_URL, headers=headers, timeout=15)
        print(f"[*] Статус ответа сайта: {response.status_code}")
        if response.status_code != 200:
            return []
    except Exception as e:
        print(f"[!] Ошибка запроса: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article")
    print(f"[*] Найдено блоков <article> на странице: {len(articles)}")

    news_items = []

    for idx, art in enumerate(articles, start=1):
        # 1. ПОИСК ИМЕНИ ИГРОКА
        player_name = ""
        # Способ А: через ссылку на игрока
        player_link = art.find("a", href=lambda h: h and ("/players/" in h or "/player/" in h))
        if player_link and player_link.get_text(strip=True):
            player_name = clean_inline_text(player_link.get_text())

        # Способ Б: через заголовки h2, h3, h4 или жирный текст
        if not player_name:
            header_tag = art.find(["h2", "h3", "h4", "h5", "strong"])
            if header_tag:
                candidate = clean_inline_text(header_tag.get_text())
                if candidate and len(candidate.split()) <= 4:
                    player_name = candidate

        # 2. ПОЛУЧЕНИЕ ВСЕГО ТЕКСТА КАРТОЧКИ ДЛЯ АНАЛИЗА
        all_text = art.get_text(separator="\n").strip()
        lines = [clean_inline_text(l) for l in all_text.split("\n") if clean_inline_text(l)]

        # Способ В: если имя всё ещё не найдено — берём первую строку карточки
        if not player_name and lines:
            first_line = lines[0]
            if "(" in first_line:
                player_name = first_line[:first_line.find("(")].strip()
            else:
                player_name = first_line

        # Очищаем имя от случайных скобок амплуа, например "Matty Beniers(Center)" -> "Matty Beniers"
        if "(" in player_name:
            player_name = player_name[:player_name.find("(")].strip()

        # 3. ПОИСК ПОЗИЦИИ (Defenseman, Center, Goalie и т.д.)
        position = "Forward"
        pos_match = re.search(
            r"\b(Defenseman|Forward|Center|Left Wing|Right Wing|Goalie|LW|RW|C|D|G)\b",
            all_text,
            re.IGNORECASE
        )
        if pos_match:
            raw_pos = pos_match.group(1).lower()
            position = POSITIONS_MAP.get(raw_pos, "Forward")

        # 4. ПОИСК КОМАНДЫ
        team = "NHL"
        for t in KNOWN_TEAMS:
            if t.lower() in all_text.lower():
                team = t
                break

        # 5. ПОИСК КАТЕГОРИИ
        cat_match = re.search(
            r"\b(Signing|Trade|Trades|Injury|Line Change|Call Up|Send Down|Roster Moves|Waiver Move|Goalie Start)\b",
            all_text,
            re.IGNORECASE
        )
        category = "News"
        if cat_match:
            c = cat_match.group(1).title()
            if c in ["Trades", "Trade"]:
                category = "Trade"
            elif c == "Roster Moves":
                category = "Call Up" if "recalled" in all_text.lower() else "Send Down"
            else:
                category = c

        # 6. ПОИСК ИСТОЧНИКА (SOURCE)
        source = ""
        source_match = re.search(r"Source:\s*([^\n]+)", all_text, re.IGNORECASE)
        if source_match:
            source = source_match.group(1).strip()
        else:
            # Ищем отметку твиттера/инсайдера
            for l in lines:
                if l.startswith("@") or "GMT" in l:
                    source = l
                    break

        # 7. ПОИСК ТЕКСТА САМОЙ НОВОСТИ
        news_text = ""
        
        # Способ А: ищем абзацы <p> внутри карточки
        p_tags = art.find_all("p")
        for p in p_tags:
            p_text = clean_inline_text(p.get_text())
            if p_text and not p_text.startswith("Source:") and p_text != player_name:
                news_text += " " + p_text
        news_text = news_text.strip()

        # Способ Б: если <p> не содержал описания, выбираем самое длинное информативное предложение
        if not news_text:
            candidates = []
            for l in lines:
                if (l != player_name and 
                    l != category and 
                    l != team and 
                    l != "|" and 
                    not l.startswith("Source:") and 
                    not l.startswith("@") and
                    len(l) > 15):
                    candidates.append(l)
            if candidates:
                # Берём самое длинное предложение — это и есть текст новости
                news_text = max(candidates, key=len)

        # Если имя или текст так и не удалось достать — пропускаем брак
        if not player_name or not news_text:
            continue

        news_items.append({
            "player": player_name,
            "position": position,
            "team": team,
            "category": category,
            "text": news_text,
            "source": source
        })

    print(f"[*] Успешно распознано новостей: {len(news_items)}")
    return news_items
