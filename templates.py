import re

SHORT_POSITIONS = {
    "Defenseman": "D", "defense": "D", "d": "D",
    "Center": "C", "c": "C",
    "Left Wing": "LW", "left wing": "LW", "lw": "LW",
    "Right Wing": "RW", "right wing": "RW", "rw": "RW",
    "Forward": "F", "forward": "F", "f": "F",
    "Goalie": "G", "goalie": "G", "g": "G"
}

TEAMS_CLEAN = {
    "anaheim": "Anaheim Ducks", "ducks": "Anaheim Ducks", "boston": "Boston Bruins", "bruins": "Boston Bruins",
    "buffalo": "Buffalo Sabres", "sabres": "Buffalo Sabres", "calgary": "Calgary Flames", "flames": "Calgary Flames",
    "carolina": "Carolina Hurricanes", "hurricanes": "Carolina Hurricanes", "chicago": "Chicago Blackhawks", "blackhawks": "Chicago Blackhawks",
    "colorado": "Colorado Avalanche", "avalanche": "Colorado Avalanche", "columbus": "Columbus Blue Jackets", "blue jackets": "Columbus Blue Jackets",
    "dallas": "Dallas Stars", "stars": "Dallas Stars", "detroit": "Detroit Red Wings", "red wings": "Detroit Red Wings",
    "edmonton": "Edmonton Oilers", "oilers": "Edmonton Oilers", "florida": "Florida Panthers", "panthers": "Florida Panthers",
    "los angeles": "Los Angeles Kings", "kings": "Los Angeles Kings", "minnesota": "Minnesota Wild", "wild": "Minnesota Wild",
    "montreal": "Montreal Canadiens", "canadiens": "Montreal Canadiens", "nashville": "Nashville Predators", "predators": "Nashville Predators",
    "new jersey": "New Jersey Devils", "devils": "New Jersey Devils", "islanders": "New York Islanders", "ny islanders": "New York Islanders",
    "rangers": "New York Rangers", "ny rangers": "New York Rangers", "ottawa": "Ottawa Senators", "senators": "Ottawa Senators",
    "philadelphia": "Philadelphia Flyers", "flyers": "Philadelphia Flyers", "pittsburgh": "Pittsburgh Penguins", "penguins": "Pittsburgh Penguins",
    "san jose": "San Jose Sharks", "sharks": "San Jose Sharks", "seattle": "Seattle Kraken", "kraken": "Seattle Kraken",
    "st louis": "St. Louis Blues", "st. louis": "St. Louis Blues", "blues": "St. Louis Blues", "tampa bay": "Tampa Bay Lightning", "lightning": "Tampa Bay Lightning",
    "toronto": "Toronto Maple Leafs", "maple leafs": "Toronto Maple Leafs", "utah": "Utah Mammoth", "mammoth": "Utah Mammoth",
    "vancouver": "Vancouver Canucks", "canucks": "Vancouver Canucks", "vegas": "Vegas Golden Knights", "golden knights": "Vegas Golden Knights",
    "washington": "Washington Capitals", "capitals": "Washington Capitals", "winnipeg": "Winnipeg Jets", "jets": "Winnipeg Jets"
}

DAYS_MAP = {
    "sunday": "в воскресенье", "monday": "во понедельник", "tuesday": "во вторник",
    "wednesday": "в среду", "thursday": "в четверг", "friday": "в пятницу",
    "saturday": "в субботу", "today": "сегодня", "tonight": "сегодня ночью"
}

INJURIES_MAP = {
    "upper-body": "травма верхней части тела", "upper body": "травма верхней части тела",
    "lower-body": "травма нижней части тела", "lower body": "травма нижней части тела",
    "undisclosed": "характер травмы не раскрывается", "illness": "болезнь",
    "knee": "травма колена", "hip": "травма бедра", "groin": "травма паха", "shoulder": "травма плеча",
    "wrist": "травма запястья", "hand": "травма кисти", "fractured skull": "перелом черепа",
    "skull fracture": "перелом черепа", "maintenance": "плановый отдых"
}

def get_day(text: str) -> str:
    for en, ru in DAYS_MAP.items():
        if re.search(rf"\b{en}\b", text, re.I):
            return ru
    return "в ближайшем матче"

def get_opponent(text: str) -> str:
    match = re.search(r"(?:vs\.?|against|in|at)\s+(?:the\s+)?([a-z\s\.\-]+)", text, re.I)
    if match:
        raw = match.group(1).lower().strip().rstrip(".,")
        for k, full in TEAMS_CLEAN.items():
            if k in raw:
                return full
    return ""

def get_injury_type(text: str) -> str:
    t = text.lower()
    for en, ru in INJURIES_MAP.items():
        if en in t:
            return ru
    return ""

def build_telegram_post(player: str, pos_en: str, team: str, category: str, text: str, source: str = "") -> str:
    pos = SHORT_POSITIONS.get(pos_en, "F")
    clean = text.strip()
    low = clean.lower()
    day = get_day(clean)
    opp = get_opponent(clean)
    opp_str = f" против {opp}" if opp else ""
    inj = get_injury_type(clean)

    # 1. СТАРТОВЫЙ ВРАТАРЬ
    if "goalie" in pos_en.lower() or "first goalie off" in low or "led the" in low:
        status = "вероятно будет стартовым вратарем" if any(x in low for x in ["led", "first goalie off", "warmup"]) else f"станет основным вратарем {day}{opp_str}"
        return f"{team}\n🥅 {player} ({pos}) {status}"

    # 2. ОПРЕДЕЛЕНИЕ СТАТУСА ТРАВМЫ В ТЕКСТЕ
    # Если игрок вернулся / тренируется без ограничений / дебютирует — травму в скобках не дублируем
    hide_inj = any(k in low for k in ["regular jersey", "full participant", "season debut", "will play", "in the lineup", "non-contact"])
    inj_str = f" ({inj})" if inj and not hide_inj else ""
    prefix = f"{player} ({pos}){inj_str}"

    # 3. ЕДИНЫЕ ШАБЛОНЫ (emoji, action)
    if "game-time decision" in low:
        emoji, act = "🤔", f"Решение по участию будет принято перед матчем {day}{opp_str}"
    elif "left" in low and "game" in low and "did not return" in low:
        emoji, act = "🚑", f"получил повреждение {day} и досрочно покинул площадку"
    elif "week-to-week" in low:
        emoji, act = "⚠️", "выбыл на несколько недель (статус week-to-week)"
    elif "out for" in low:
        m = re.search(r"out for (?:at least )?(?:the next )?(\d+[\-\d]*\s*(?:days|weeks))", low)
        period = m.group(1).replace("days", "дней").replace("weeks", "недель") if m else "неопределенный срок"
        emoji, act = "⚠️", f"пропустит как минимум {period}"
    elif "non-contact jersey" in low:
        emoji, act = "🟡", f"тренировался в бесконтактном свитере {day}"
    elif "full participant" in low or "regular jersey" in low:
        emoji, act = "🟢", f"тренировался в общей группе без ограничений {day}"
    elif "missed" in low and "morning skate" in low:
        emoji, act = "➖", f"пропустил утреннюю раскатку {day}"
    elif "missed" in low and "practice" in low:
        emoji, act = "➖", f"пропустил тренировку {day}"
    elif "will travel" in low and "road trip" in low:
        emoji, act = "✈️", "отправится с командой на предстоящую выездную серию"
    elif "chance to return" in low or "could return" in low:
        target = "к концу недели" if "end of the week" in low else (f"{day}{opp_str}" if day != "в ближайшем матче" else "в ближайшее время")
        emoji, act = "⏳", f"может вернуться в строй {target}"
    elif "season debut" in low:
        emoji, act = "⭐️", f"проведёт свой первый матч в сезоне {day}{opp_str}"
    elif ("will play" in low or "in the" in low and "lineup" in low) and "not play" not in low:
        emoji, act = "✅", f"сыграет {day}{opp_str}"
    elif any(k in low for k in ["remain out", "is out", "will not play", "ruled out"]):
        dt = " (day-to-day)" if "day-to-day" in low else ""
        emoji, act = "⛔", f"не сыграет {day}{opp_str}{dt}"
    elif "day-to-day" in low:
        emoji, act = "🚫", "статус day-to-day"
    elif "activated from ir" in low:
        emoji, act = "✅", "активирован из списка травмированных"
    elif "placed on ir" in low or "injured reserve" in low:
        emoji, act = "🚫", "внесен в список травмированных"
    else:
        emoji, act = "ℹ️", clean

    # ЕДИНЫЙ ВЫВОД ДЛЯ ВСЕХ ПОСТОВ
    return f"{team}\n{emoji} {prefix} {act}"
