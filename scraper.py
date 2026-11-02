import requests
from bs4 import BeautifulSoup
from config import DAILYFACEOFF_URL, USER_AGENT

def fetch_player_news() -> list[dict]:
    """Скрейпит свежие новости с DailyFaceoff"""
    headers = {"User-Agent": USER_AGENT}
    try:
        response = requests.get(DAILYFACEOFF_URL, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"[!] Ошибка запроса к сайту: {response.status_code}")
            return []
    except Exception as e:
        print(f"[!] Исключение при запросе к сайту: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    news_items = []

    # DailyFaceoff упаковывает карточки в контейнеры новостей
    # Для устойчивости ищем блоки со структурой заголовка игрока
    articles = soup.find_all("article") or soup.find_all("div", class_=lambda c: c and "news" in c.lower())

    for art in articles:
        text_content = art.get_text(separator="\n").strip()
        lines = [line.strip() for line in text_content.split("\n") if line.strip()]
        
        # Минимальная валидация карточки (игрок, команда, текст)
        if len(lines) < 4:
            continue

        # Парсинг строки "Player Name(Position)"
        first_line = lines[0]
        if "(" not in first_line or ")" not in first_line:
            continue
            
        player_name = first_line[:first_line.find("(")].strip()
        position = first_line[first_line.find("(")+1 : first_line.find(")")].strip()
        
        # Поиск команды и категории
        team = lines[1].replace("|", "").strip() if len(lines) > 1 else "NHL"
        category = lines[2].strip() if len(lines) > 2 else "News"
        
        # Текст новости обычно идет следом
        desc_lines = []
        source = ""
        for line in lines[3:]:
            if line.startswith("Source:") or line.startswith("@"):
                source = line.replace("Source:", "").strip()
                break
            if line != player_name and line != category:
                desc_lines.append(line)

        news_text = " ".join(desc_lines)
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
