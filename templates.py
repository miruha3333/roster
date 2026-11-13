import os
import re
from typing import Optional, Set, List, Dict, Any

# Безопасная подгрузка ключа из .env (если файл существует локально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Попытка подключить библиотеку OpenAI для AI-контроля постов
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# 1. Лаконичные обозначения позиций
SHORT_POSITIONS = {
    "Defenseman": "D", "defense": "D", "d": "D",
    "Center": "C", "c": "C",
    "Left Wing": "LW", "left wing": "LW", "lw": "LW",
    "Right Wing": "RW", "right wing": "RW", "rw": "RW",
    "Forward": "F", "forward": "F", "f": "F",
    "Goalie": "G", "goalie": "G", "g": "G"
}

# 2. Полные названия клубов НХЛ и алиасы
TEAMS_CLEAN = {
    "anaheim": "Anaheim Ducks", "ducks": "Anaheim Ducks",
    "boston": "Boston Bruins", "bruins": "Boston Bruins",
    "buffalo": "Buffalo Sabres", "sabres": "Buffalo Sabres",
    "calgary": "Calgary Flames", "flames": "Calgary Flames",
    "carolina": "Carolina Hurricanes", "hurricanes": "Carolina Hurricanes",
    "chicago": "Chicago Blackhawks", "blackhawks": "Chicago Blackhawks",
    "colorado": "Colorado Avalanche", "avalanche": "Colorado Avalanche",
    "columbus": "Columbus Blue Jackets", "blue jackets": "Columbus Blue Jackets",
    "dallas": "Dallas Stars", "stars": "Dallas Stars",
    "detroit": "Detroit Red Wings", "red wings": "Detroit Red Wings",
    "edmonton": "Edmonton Oilers", "oilers": "Edmonton Oilers",
    "florida": "Florida Panthers", "panthers": "Florida Panthers",
    "los angeles": "Los Angeles Kings", "kings": "Los Angeles Kings",
    "minnesota": "Minnesota Wild", "wild": "Minnesota Wild",
    "montreal": "Montreal Canadiens", "canadiens": "Montreal Canadiens",
    "nashville": "Nashville Predators", "predators": "Nashville Predators",
    "new jersey": "New Jersey Devils", "devils": "New Jersey Devils",
    "islanders": "New York Islanders", "ny islanders": "New York Islanders",
    "rangers": "New York Rangers", "ny rangers": "New York Rangers", "new york": "New York Rangers",
    "ottawa": "Ottawa Senators", "senators": "Ottawa Senators",
    "philadelphia": "Philadelphia Flyers", "flyers": "Philadelphia Flyers",
    "pittsburgh": "Pittsburgh Penguins", "penguins": "Pittsburgh Penguins",
    "san jose": "San Jose Sharks", "sharks": "San Jose Sharks",
    "seattle": "Seattle Kraken", "kraken": "Seattle Kraken",
    "st louis": "St. Louis Blues", "st. louis": "St. Louis Blues", "blues": "St. Louis Blues",
    "tampa bay": "Tampa Bay Lightning", "lightning": "Tampa Bay Lightning",
    "toronto": "Toronto Maple Leafs", "maple leafs": "Toronto Maple Leafs",
    "utah": "Utah Mammoth", "mammoth": "Utah Mammoth",
    "vancouver": "Vancouver Canucks", "canucks": "Vancouver Canucks",
    "vegas": "Vegas Golden Knights", "golden knights": "Vegas Golden Knights",
    "washington": "Washington Capitals", "capitals": "Washington Capitals",
    "winnipeg": "Winnipeg Jets", "jets": "Winnipeg Jets"
}

# 3. Дни недели
DAYS_MAP = {
    "sunday": "в воскресенье", "monday": "в понедельник", "tuesday": "во вторник",
    "wednesday": "в среду", "thursday": "в четверг", "friday": "в пятницу",
    "saturday": "в субботу", "today": "сегодня", "tonight": "сегодня ночью"
}

# 4. Характер травм
INJURIES_MAP = {
    "upper-body": "травма верхней части тела", "upper body": "травма верхней части тела",
    "lower-body": "травма нижней части тела", "lower body": "травма нижней части тела",
    "undisclosed": "характер травмы не раскрывается", "illness": "болезнь",
    "knee": "травма колена", "hip": "травма бедра", "groin": "травма паха", "shoulder": "травма плеча",
    "wrist": "травма запястья", "hand": "травма кисти", "fractured skull": "перелом черепа",
    "skull fracture": "перелом черепа", "maintenance": "плановый отдых"
}

# 5. Числительные словами для контрактов
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8
}

# Хранилище опубликованных ключей
SEEN_EVENTS: Set[str] = set()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ai_client = OpenAI(api_key=OPENAI_KEY) if (OpenAI and OPENAI_KEY) else None

AI_SYSTEM_PROMPT = """
Ты — строгий редактор русскоязычного Telegram-канала о хоккее и НХЛ.
Тебе дана хоккейная заметка на английском. Твоя задача — извлечь ТОЛЬКО СУТЬ события и вернуть СТРОГО 2 строки:

Строка 1: Полное название команды игрока на английском (например: Vancouver Canucks)
Строка 2: {Эмодзи} Имя Фамилия (Амплуа на англ: D, C, LW, RW, G) {суть события на русском языке}

Допустимые форматы для строки 2:
- 🥅 Вратари: станет основным вратарем в [день] против [Соперник] ИЛИ вероятно будет стартовым вратарем
- 🚑 Травма в игре: получил повреждение [день] и досрочно покинул площадку
- ⛔ Травма: не сыграет в [день] против [Соперник]
- 🟢 Состав: возвращается в состав в [день] против [Соперник]
- ❌ Запас: останется в запасе в [день]
- 🚀 Фарм: вызван из [Клуб] (AHL)
- ⬇️ Фарм: отправлен в [Клуб] (AHL)
- ✍️ Контракт: подписал контракт на [X] года/лет ($[Сумма])

ВАЖНО:
1. Выкидывай всю "воду", статистику предыдущих матчей, цитаты, букмекерские коэффициенты (-122 favourites).
2. Не путай команду игрока и команду соперника (после слова against / vs).
3. Имя хоккеиста и амплуа ВСЕГДА идут первыми в строке 2 сразу после эмодзи!
4. Если в тексте НЕТ конкретного события по составу, верни ровно одно слово: SKIP
"""

def ai_format_or_filter(player: str, pos: str, team: str, text: str) -> Optional[str]:
    """Нейросеть-контролер: форматирует текст в 2 строки без воды либо отсекает мусор (SKIP)"""
    if not ai_client:
        return None

    try:
        user_msg = f"Игрок: {player} ({pos})\nКоманда из заголовка: {team}\nТекст новости:\n{text}"
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.1,
            max_tokens=120
        )
        res = response.choices[0].message.content.strip()
        if "SKIP" in res or res == "SKIP":
            return None
        return res
    except Exception as e:
        print(f"[AI Controller Error]: {e}")
        return None

def format_years(years: int) -> str:
    """Возвращает русское склонение для срока контракта"""
    if years == 1:
        return "1 год"
    elif 2 <= years <= 4:
        return f"{years} года"
    return f"{years} лет"

def clean_trade_assets(text: str) -> str:
    """Переводит драфт-пики и условия удержания зарплаты на русский язык"""
    t = text.strip().rstrip(".,")
    t = re.sub(r"(?:a\s+)?(\d{4})\s+(\d+)(?:st|nd|rd|th)[-\s]round\s+pick(?:\s*\([^\)]+\))?", r"драфт-пик \2-го раунда (\1)", t, flags=re.I)
    t = re.sub(r"(?:a\s+)?(\d+)(?:st|nd|rd|th)[-\s]round\s+pick(?:\s*\([^\)]+\))?", r"драфт-пик \1-го раунда", t, flags=re.I)
    t = re.sub(r"\((\d+)%\s+(?:retained\s+salary|salary\s+retained)\)", r"(с удержанием \1% зарплаты)", t, flags=re.I)
    t = re.sub(r"\((?:some\s+retained\s+salary|some\s+salary\s+retained)\)", r"(с удержанием части зарплаты)", t, flags=re.I)
    t = re.sub(r",?\s+and\s+", " и ", t, flags=re.I)
    return t

def get_day(text: str) -> str:
    """Определяет день недели"""
    for en, ru in DAYS_MAP.items():
        if re.search(rf"\b{en}\b", text, re.I):
            return ru
    return ""

def get_opponent(text: str) -> str:
    """
    Ищет клуб соперника.
    Исключен предлог 'at' во избежание путаницы с 'at morning skate'.
    """
    # Ищем строго после vs, against или предлога in перед названием города
    match = re.search(r"(?:vs[.,]?|against)\s+(?:the\s+)?([a-z\s\.\-]+)", text, re.I)
    if not match:
        match = re.search(r"\bin\s+(?:the\s+)?([a-z\s\.\-]+)", text, re.I)
    
    if match:
        raw_opp = match.group(1).lower().strip().rstrip(".,")
        # Отсекаем ложные срабатывания
        if any(bad in raw_opp for bad in ["morning skate", "practice", "overtime", "lineup"]):
            return ""
        for key, full_team in TEAMS_CLEAN.items():
            if key in raw_opp:
                return full_team
    return ""

def get_injury_type(text: str) -> str:
    """Определяет характер травмы"""
    lower = text.lower()
    for en, ru in INJURIES_MAP.items():
        if en in lower:
            return ru
    return ""

def extract_farm_team(text: str, action: str = "from") -> str:
    """Точно извлекает полное название фарм-клуба без обрезки слов"""
    if action == "from":
        m = re.search(r"from\s+(?:the\s+)?([A-Za-z0-9\s\.\-]+?)(?:\s*\((?:AHL|ECHL|OHL|WHL)\)|[\.\n$])", text, re.I)
    else:
        m = re.search(r"(?:to|at|report to)\s+(?:the\s+)?([A-Za-z0-9\s\.\-]+?)(?:\s*\((?:AHL|ECHL|OHL|WHL)\)|[\.\n$])", text, re.I)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"^(loan on|loan to|assignment to)\s+", "", name, flags=re.I)
        return name
    return "фарм-клуб"

def filter_unique_trades(posts_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Оставляет только 1 самую полную карточку на каждый мега-обмен"""
    unique_trades = {}
    other_posts = []

    for item in posts_data:
        text_raw = item.get("text", "")
        text_low = text_raw.lower()
        if item.get("category") == "Trade" or "acquired" in text_low:
            clubs = []
            for k, full in TEAMS_CLEAN.items():
                if k in text_low and full not in clubs:
                    clubs.append(full)
            if len(clubs) >= 2:
                trade_id = tuple(sorted(clubs[:2]))
                if trade_id not in unique_trades or len(text_raw) > len(unique_trades[trade_id]["text"]):
                    unique_trades[trade_id] = item
            else:
                other_posts.append(item)
        else:
            other_posts.append(item)

    return list(unique_trades.values()) + other_posts

def build_telegram_post(
    player: str, 
    pos_en: str, 
    team: str, 
    category: str, 
    text: str, 
    source: str = "",
    check_duplicates: bool = True
) -> Optional[str]:
    """
    Формирует лаконичный пост для Telegram в строгом едином стиле.
    """
    pos = SHORT_POSITIONS.get(pos_en, "F")
    
    # Нормализуем текст (заменяем типографские апострофы на стандартные)
    norm_text = text.replace("’", "'").replace("`", "'")
    
    # 1. Извлечение только заголовка
    span_match = re.search(r'<span[^>]*class="[^"]*font-bold[^"]*"[^>]*>(.*?)</span>', norm_text, re.I | re.S)
    if span_match:
        clean = re.sub(r'<[^>]+>', '', span_match.group(1)).strip()
    else:
        clean = norm_text.strip().split("\n\n")[0].split("\n")[0].strip()

    low = clean.lower()
    full_low = norm_text.lower()
    day = get_day(clean) or get_day(norm_text)
    opp = get_opponent(clean) or get_opponent(norm_text)

    # Защита от подмены клуба: если у игрока уже есть валидный клуб, не перезаписываем его!
    if team.lower() in ["signing", "injury", "line change", "trade", "call up", "send down", "waiver move", "goalie start", "free agent", ""]:
        for k, full in TEAMS_CLEAN.items():
            # Не берем клуб, если он идет после слова against (это соперник!)
            if f"against the {k}" in full_low or f"against {k}" in full_low or f"vs. {k}" in full_low:
                continue
            if f"the {k}" in full_low or f"with the {k}" in full_low or f"with {k}" in full_low:
                team = full
                break

    # Соперник не может совпадать со своей же командой
    if opp and team and opp.lower() == team.lower():
        opp = ""

    # Связка дня и соперника
    opp_str = f" против {opp}" if opp else ""
    if day and opp:
        when_where = f" {day}{opp_str}"
    elif day:
        when_where = f" {day}"
    elif opp:
        when_where = f"{opp_str}"
    else:
        when_where = ""

    # Скрытие травмы для не-травматических статусов
    inj = get_injury_type(clean)
    hide_inj = any(k in low for k in [
        "regular jersey", "full participant", "season debut", "will play", 
        "in the lineup", "non-contact", "draw into", "draw back", 
        "return to the lineup", "scratch", "recalled", "assigned", "loaned", "reassigned",
        "contract", "signed", "deal", "acquired", "trade", "waiver", "claimed", "start", "crease"
    ])
    inj_str = f" ({inj})" if inj and not hide_inj else ""
    
    prefix = f"{player} ({pos}){inj_str}"
    event_type = "unknown"

    # ==================== 1. ТРАВМЫ ВО ВРЕМЯ МАТЧА ====================
    if any(k in low for k in ["left", "leaves", "exited", "exits", "knocked out of"]) and any(g in low for g in ["game", "ice", "match"]):
        event_type = "left_game"
        day_str = f" {day}" if day else ""
        emoji, act = "🚑", f"получил повреждение{day_str} и досрочно покинул площадку"

    # ==================== 2. СТАРТОВЫЕ ВРАТАРИ ====================
    elif "goalie" in pos_en.lower() or any(k in low for k in ["start", "crease", "in net", "pipes"]):
        if any(x in low for x in ["led the", "first goalie off", "warmup", "starter's crease", "starter crease", "starter at"]):
            event_type, emoji, act = "goalie_probable", "🥅", "вероятно будет стартовым вратарем"
        elif any(x in low for x in [
            "start", "starting", "in net", "between the pipes", "onto the ice",
            "return to the crease", "returns to the crease", "back in the crease",
            "in the crease", "gets the nod", "takes the crease", "confirmed to start"
        ]):
            event_type, emoji, act = "goalie_starter", "🥅", f"станет основным вратарем{when_where}"

    # ==================== 3. ДРАФТ ОТКАЗОВ (WAIVER MOVES) ====================
    claim_match_direct = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?(?:claimed|acquired)\s+(.+?)\s+off\s+(?:of\s+)?waivers\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)[\.\s$]", clean, re.I)
    claim_match_inv = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?claimed\s+(.+?)\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)\s+(?:off\s+(?:of\s+)?waivers|on\s+[a-z]+)[\.\s$]", clean, re.I)

    if (claim_match_direct or claim_match_inv) and event_type == "unknown":
        m = claim_match_direct if claim_match_direct else claim_match_inv
        who_claimed_raw, who_got, from_c_raw = m.groups()
        for k, full in TEAMS_CLEAN.items():
            if k in who_claimed_raw.lower():
                team = full
            if k in from_c_raw.lower():
                from_c_raw = full
        day_str = f" {day}" if day else ""
        event_type = f"waiver_claim:{from_c_raw.lower()}:{team.lower()}"
        emoji, act = "📋", f"забран с драфта отказов у «{from_c_raw.strip()}»{day_str}"

    elif ("unconditional waivers" in low or ("waivers" in low and "contract termination" in low)) and event_type == "unknown":
        event_type = "waiver_unconditional"
        for k, full in TEAMS_CLEAN.items():
            if f"the {k}" in full_low or f"{k} recently" in full_low or f"{k} will" in full_low:
                team = full
                break
        day_str = f" {day}" if day else ""
        emoji, act = "❌", f"выставлен на драфт отказов для расторжения контракта{day_str}"

    elif ("cleared waivers" in low and any(k in low for k in ["assigned", "loaned", "reassigned", "report to"])) and event_type == "unknown":
        event_type = "cleared_assigned"
        dest = extract_farm_team(clean, action="to")
        for k, full in TEAMS_CLEAN.items():
            if f"the {k}" in full_low or f"{k} placed" in full_low:
                team = full
                break
        emoji, act = "⬇️", f"прошёл драфт отказов и отправлен в {dest} (AHL)"

    elif ("placed on waivers" in low or "placing" in low and "waivers" in low or "placed" in low and "waivers" in low) and event_type == "unknown":
        event_type = "waiver_placed"
        for k, full in TEAMS_CLEAN.items():
            if f"the {k}" in full_low or f"{k} placed" in full_low:
                team = full
                break
        day_str = f" {day}" if day else ""
        emoji, act = "⚠️", f"выставлен на драфт отказов (waivers){day_str}"

    # ==================== 4. КОМБИНИРОВАННЫЕ СТАТУСЫ IR + AHL ====================
    elif ("activated from ir" in low and any(k in low for k in ["assigned", "loaned", "reassigned"])) and event_type == "unknown":
        event_type = "ir_activated_assigned"
        dest = extract_farm_team(clean, action="to")
        emoji, act = "✅", f"активирован из списка травмированных и отправлен в {dest} (AHL)"

    # ==================== 5. ВЫЗОВЫ И ОТПРАВКИ (CALL UP / SEND DOWN) ====================
    elif "recalled" in low and event_type == "unknown":
        event_type = "recalled"
        farm = extract_farm_team(clean, action="from")
        emoji, act = "🚀", f"вызван из {farm} (AHL)"

    elif any(k in low for k in ["assigned", "loaned", "reassigned"]) and event_type == "unknown":
        event_type = "assigned"
        dest = extract_farm_team(clean, action="to")
        emoji, act = "⬇️", f"отправлен в {dest} (AHL)"

    # ==================== 6. ОБМЕНЫ (TRADES) ====================
    elif ("acquired" in low and ("from" in low or "for" in low)) and event_type == "unknown":
        event_type = "trade"
        t_match = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?acquired\s+(.+?)\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)\s+for\s+(.+?)[\.\s$]", clean, re.I)
        if t_match:
            acq_raw, got_raw, from_raw, for_raw = t_match.groups()
            acq_team = team
            from_team = "клуба соперника"
            for k, full in TEAMS_CLEAN.items():
                if k in acq_raw.lower():
                    acq_team = full
                if k in from_raw.lower():
                    from_team = full

            got_clean = clean_trade_assets(got_raw)
            for_clean = clean_trade_assets(for_raw)

            if player.lower() in got_raw.lower():
                team = acq_team
                emoji, act = "🔄", f"выменян у {from_team} в обмен на {for_clean}"
            else:
                team = from_team
                emoji, act = "🔄", f"обменян в {acq_team} на {got_clean}"
        else:
            emoji, act = "🔄", "стал участником обмена"

    # ==================== 7. ПОДПИСАНИЯ КОНТРАКТОВ (SIGNINGS) ====================
    elif any(k in low for k in ["contract", "deal", "extension", "signed"]) and "claim" not in low and event_type == "unknown":
        event_type = "signing"
        y_match = re.search(r"(\d+|one|two|three|four|five|six|seven|eight)-year", low)
        years_str = ""
        if y_match:
            val = y_match.group(1)
            years_num = int(val) if val.isdigit() else NUM_WORDS.get(val, 1)
            years_str = f" на {format_years(years_num)}"

        money_str = ""
        aav_total_match = re.search(r"(\$[\d,\.]+(?:M|K)?\s*AAV)\s*\(([\$\d,\.]+(?:M|K)?\s*total)\)", clean, re.I)
        aav_match = re.search(r"(\$[\d,\.]+(?:M|K)?\s*AAV)", clean, re.I)
        std_money_match = re.search(r"(\$[\d,]+(?:\.\d+)?(?:M|K)?)", clean)

        if aav_total_match:
            money_str = f" ({aav_total_match.group(1)} / {aav_total_match.group(2)})"
        elif aav_match:
            money_str = f" ({aav_match.group(1)})"
        elif std_money_match:
            money_str = f" ({std_money_match.group(1)})"

        emoji, act = "✍️", f"подписал контракт{years_str}{money_str}".strip()

    # ==================== 8. СПИСКИ ТРАВМИРОВАННЫХ (IR) ====================
    elif ("activated from ir" in low or "activated from injured reserve" in low) and event_type == "unknown":
        event_type, emoji, act = "ir_activated", "✅", "активирован из списка травмированных"
    elif ("placed on ir" in low or ("placed" in low and "injured reserve" in low)) and event_type == "unknown":
        event_type, emoji, act = "ir_placed", "🚫", "внесен в список травмированных"

    # ==================== 9. РЕШЕНИЕ ПЕРЕД МАТЧЕМ (GTD) ====================
    elif any(k in low for k in ["game-time decision", "game time decision", "questionable", "doubtful", "up in the air"]) and event_type == "unknown":
        event_type = "gtd"
        day_opp = f" {day}{opp_str}".strip() if day else opp_str.strip()
        match_str = f" перед матчем {day_opp}" if day_opp else " перед игрой"
        emoji, act = "🤔", f"Решение по участию будет принято{match_str}"

    # ==================== 10. ОПЕРАЦИИ ====================
    elif ("surgery" in low or "underwent" in low) and event_type == "unknown":
        event_type = "surgery"
        emoji, act = "⚠️", "перенёс операцию и выбыл из строя"

    # ==================== 11. СРОКИ ВЫБЫВАНИЯ ====================
    elif "week-to-week" in low and event_type == "unknown":
        event_type, emoji, act = "week_to_week", "⚠️", "выбыл на несколько недель (статус week-to-week)"
    elif "out for" in low and event_type == "unknown":
        event_type = "out_for"
        m = re.search(r"out for (?:at least )?(?:the next )?(\d+[\-\d]*\s*(?:days|weeks|months))", low)
        period = m.group(1).replace("days", "дней").replace("weeks", "недель").replace("months", "месяцев") if m else "неопределенный срок"
        emoji, act = "⚠️", f"пропустит как минимум {period}"

    # ==================== 12. ТРЕНИРОВКИ И РАСКАТКИ ====================
    elif "non-contact jersey" in low and event_type == "unknown":
        event_type, emoji, act = "practice_noncontact", "🟡", f"тренировался в бесконтактном свитере{f' {day}' if day else ''}"
    elif ("full participant" in low or "regular jersey" in low) and event_type == "unknown":
        event_type, emoji, act = "practice_full", "🟢", f"тренировался в общей группе без ограничений{f' {day}' if day else ''}"
    elif "missed" in low and "morning skate" in low and event_type == "unknown":
        event_type, emoji, act = "missed_skate", "➖", f"пропустил утреннюю раскатку{f' {day}' if day else ''}"
    elif "missed" in low and "practice" in low and event_type == "unknown":
        event_type, emoji, act = "missed_practice", "➖", f"пропустил тренировку{f' {day}' if day else ''}"

    # ==================== 13. ВЫЕЗДЫ И ВОЗВРАЩЕНИЕ ====================
    elif "will travel" in low and "road trip" in low and event_type == "unknown":
        event_type, emoji, act = "travel_trip", "✈️", "отправится с командой на предстоящую выездную серию"
    elif ("chance to return" in low or "could return" in low) and event_type == "unknown":
        event_type = "chance_return"
        target = "к концу недели" if "end of the week" in low else (when_where.strip() if when_where else "в ближайшее время")
        emoji, act = "⏳", f"может вернуться в строй {target}"

    # ==================== 14. ДЕБЮТЫ ====================
    elif "season debut" in low and event_type == "unknown":
        event_type, emoji, act = "season_debut", "⭐️", f"проведёт свой первый матч в сезоне{when_where}"
    elif "debut" in low and event_type == "unknown":
        event_type = "debut"
        if "nhl debut" in low:
            emoji, act = "⭐️", f"проведёт свой дебютный матч в карьере в НХЛ{when_where}"
        else:
            emoji, act = "⭐️", f"проведёт свой дебютный матч за клуб{when_where}"

    # ==================== 15. ЗВЕНЬЯ / ЗАПАС / ВОЗВРАЩЕНИЕ ====================
    elif "scratch" in low and event_type == "unknown":
        event_type, emoji, act = "scratch", "❌", f"останется в запасе{when_where}"
    elif any(k in low for k in ["draw back into", "return to the lineup", "re-enter the lineup", "enter the lineup", "draw into", "draw in"]) and event_type == "unknown":
        event_type, emoji, act = "lineup_return", "🟢", f"возвращается в состав{when_where}"
    elif ("will play" in low or ("in the" in low and "lineup" in low)) and "will not play" not in low and event_type == "unknown":
        event_type, emoji, act = "will_play", "✅", f"сыграет{when_where}"

    # ==================== 16. НЕ СЫГРАЕТ / OUT / DAY-TO-DAY ====================
    elif any(k in low for k in ["remain out", "is out", "will not play", "ruled out", "sidelined with"]) and event_type == "unknown":
        event_type = "out"
        dt = " (day-to-day)" if "day-to-day" in low else ""
        emoji, act = "⛔", f"не сыграет{when_where}{dt}"
    elif "day-to-day" in low and event_type == "unknown":
        event_type, emoji, act = "day_to_day", "🚫", "статус day-to-day"

    # ==================== 17. НЕПОНЯТНЫЙ ТЕКСТ -> СТРОГИЙ КОНТРОЛЬ ====================
    elif event_type == "unknown":
        ai_post = ai_format_or_filter(player, pos, team, norm_text)
        if ai_post:
            return ai_post
        return None

    # ==================== УМНАЯ ПРОВЕРКА НА ДУБЛИ ====================
    if check_duplicates:
        if event_type == "trade" and "acq_team" in locals() and "from_team" in locals():
            clubs = sorted([acq_team.lower(), from_team.lower()])
            dedup_key = f"trade:{clubs[0]}:{clubs[1]}"
        elif "waiver_claim" in event_type:
            dedup_key = f"{player.strip().lower()}:{event_type}"
        else:
            dedup_key = f"{player.strip().lower()}:{event_type}"

        if dedup_key in SEEN_EVENTS:
            return None
        SEEN_EVENTS.add(dedup_key)

    return f"{team}\n{emoji} {prefix} {act}"
