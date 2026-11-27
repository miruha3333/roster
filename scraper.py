import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict

URL = "https://www.dailyfaceoff.com/hockey-player-news"

KNOWN_CATEGORIES = [
    "Goalie Start",
    "Line Change",
    "Waiver Move",
    "Send Down",
    "Call Up",
    "Injury",
    "Signing",
    "Trade",
]


def _has_all_classes(tag, required_classes: List[str]) -> bool:
    """Проверяет, что у HTML-элемента присутствуют все нужные CSS-классы."""
    classes = tag.get("class") or []
    return all(cls in classes for cls in required_classes)


def _extract_header_info(article) -> tuple[str, str, str, object]:
    """
    Читает строго блок <div class="flex flex-row items-end gap-1">:
    'Dan Vladar (Goalie) | Philadelphia Flyers' -> (player, position, team, header_div)
    """
    header_div = article.find(
        "div",
        class_=lambda c: c and all(x in c for x in ["flex", "flex-row", "items-end", "gap-1"]),
    )

    if header_div:
        raw_header = header_div.get_text(" ", strip=True)
        m = re.match(r"^(.+?)\s*\(([^)]+)\)\s*\|?\s*(.+)$", raw_header)
        if m:
            player = m.group(1).strip()
            position = m.group(2).strip()
            team = m.group(3).strip(" |•-")
            return player, position, team, header_div

    return "", "", "", header_div


def _extract_category(article, content_div, header_div) -> str:
    """Находит категорию новости (Injury, Goalie Start, Line Change и т.д.)."""
    search_root = content_div if content_div else article
    for el in search_root.find_all(["span", "div", "p"]):
        if header_div and (el == header_div or el in header_div.descendants):
            continue
        txt = el.get_text(" ", strip=True)
        for cat in KNOWN_CATEGORIES:
            if txt.lower() == cat.lower():
                return cat
    return "News"


def _extract_bold_headline(article, content_div, header_div, player: str) -> str:
    """
    Читает строго <span class="font-bold"> внутри основного блока новости,
    игнорируя имя игрока в шапке и весь длинный текст ниже.
    """
    search_root = content_div if content_div else article

    for sp in search_root.find_all("span", class_=lambda c: c and "font-bold" in c):
        # Исключаем жирный текст, который находится внутри шапки игрока
        if header_div and (sp == header_div or sp in header_div.descendants):
            continue

        txt = sp.get_text(" ", strip=True)
        if not txt:
            continue
        if player and txt.lower() == player.lower():
            continue
        if any(txt.lower() == cat.lower() for cat in KNOWN_CATEGORIES):
            continue

        return txt

    return ""


def fetch_player_news() -> List[Dict[str, str]]:
    """Скачивает и парсит новости с DailyFaceoff строго по двум целевым блокам."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(URL, headers=headers, timeout=15)
        print(f"[*] Статус ответа сайта: {response.status_code}")
        if response.status_code != 200:
            return []
    except Exception as e:
        print(f"[!] Ошибка запроса к сайту: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.find_all("article")
    print(f"[*] Найдено блоков <article> на странице: {len(articles)}")

    news_list: List[Dict[str, str]] = []

    for article in articles:
        # 1. Блок <div class="flex flex-row items-end gap-1">
        player, position, team, header_div = _extract_header_info(article)
        if not player or not team:
            continue

        # 2. Контейнер <div class="flex w-full shrink flex-col justify-between gap-2">
        content_div = article.find(
            "div",
            class_=lambda c: c and all(x in c for x in ["flex", "w-full", "shrink", "flex-col", "justify-between", "gap-2"]),
        )

        # 3. Жирный заголовок <span class="font-bold"> (нижний большой текст не трогаем вообще)
        headline = _extract_bold_headline(article, content_div, header_div, player)
        if not headline:
            continue

        # 4. Категория
        category = _extract_category(article, content_div, header_div)

        news_list.append(
            {
                "player": player,
                "position": position,
                "team": team,
                "category": category,
                "text": headline,
                "source": "",
            }
        )

    print(f"[*] Успешно распознано новостей: {len(news_list)}")
    return news_list
