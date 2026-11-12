import re
from typing import Optional, Set

# 1. Лаконичные обозначения позиций
SHORT_POSITIONS = {
    "Defenseman": "D", "defense": "D", "d": "D",
    "Center": "C", "c": "C",
    "Left Wing": "LW", "left wing": "LW", "lw": "LW",
    "Right Wing": "RW", "right wing": "RW", "rw": "RW",
    "Forward": "F", "forward": "F", "f": "F",
    "Goalie": "G", "goalie": "G", "g": "G"
}

# 2. Полные названия клубов НХЛ и частые алиасы
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

# 5. Числительные словами для сроков контрактов
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8
}

# Хранилище опубликованных ключей для предотвращения дублей
SEEN_EVENTS: Set[str] = set()

def format_years(years: int) -> str:
    """Корректное склонение лет контракта"""
    if years == 1:
        return "1 год"
    elif 2 <= years <= 4:
        return f"{years} года"
    return f"{years} лет"

def clean_trade_assets(text: str) -> str:
    """Адаптирует активы обмена: драфт-пики, удержание зарплаты, союзы"""
    t = text.strip().rstrip(".,")
    # Драфт-пики с годом: a 2029 2nd Round Pick -> драфт-пик 2-го раунда (2029)
    t = re.sub(r"(?:a\s+)?(\d{4})\s+(\d+)(?:st|nd|rd|th)[-\s]round\s+pick(?:\s*\([^\)]+\))?", r"драфт-пик \2-го раунда (\1)", t, flags=re.I)
    # Драфт-пики без года: a 2nd-round pick -> драфт-пик 2-го раунда
    t = re.sub(r"(?:a\s+)?(\d+)(?:st|nd|rd|th)[-\s]round\s+pick(?:\s*\([^\)]+\))?", r"драфт-пик \1-го раунда", t, flags=re.I)
    # Удержание зарплаты
    t = re.sub(r"\((\d+)%\s+(?:retained\s+salary|salary\s+retained)\)", r"(с удержанием \1% зарплаты)", t, flags=re.I)
    t = re.sub(r"\((?:some\s+retained\s+salary|some\s+salary\s+retained)\)", r"(с удержанием части зарплаты)", t, flags=re.I)
    # Союз "и"
    t = re.sub(r",?\s+and\s+", " и ", t, flags=re.I)
    return t

def get_day(text: str) -> str:
    """Определяет день недели"""
    for en, ru in DAYS_MAP.items():
        if re.search(rf"\b{en}\b", text, re.I):
            return ru
    return ""

def get_opponent(text: str) -> str:
    """Ищет соперника с учетом опечаток (vs., vs,) и предлогов (in, at, against)"""
    match = re.search(r"(?:vs[.,]?|against|in|at)\s+(?:the\s+)?([a-z\s\.\-]+)", text, re.I)
    if match:
        raw_opp = match.group(1).lower().strip().rstrip(".,")
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
    Генерирует пост строго по единому формату:
    {Команда}
    {Эмодзи} {Игрок} ({Амплуа}){Травма} {Действие / Соперник / Дата}

    Если check_duplicates=True и новость по игроку/событию уже обрабатывалась — возвращает None.
    """
    pos = SHORT_POSITIONS.get(pos_en, "F")
    clean = text.strip()
    low = clean.lower()
    day = get_day(clean)
    opp = get_opponent(clean)

    # Автоисправление названия команды при сбое метаданных
    if team.lower() in ["signing", "injury", "line change", "trade", ""]:
        for k, full in TEAMS_CLEAN.items():
            if f"with the {k}" in low or f"with {k}" in low or f"the {k}" in low:
                team = full
                break

    # Формирование связки дня и соперника
    opp_str = f" против {opp}" if opp else ""
    if day and opp:
        when_where = f" {day}{opp_str}"
    elif day:
        when_where = f" {day}"
    elif opp:
        when_where = f"{opp_str}"
    else:
        when_where = ""

    # Скрытие травмы для здоровых игроков / подписаний / обменов
    inj = get_injury_type(clean)
    hide_inj = any(k in low for k in [
        "regular jersey", "full participant", "season debut", "will play", 
        "in the lineup", "non-contact", "draw into", "draw back", 
        "return to the lineup", "scratch", "recalled", "assigned", "loaned",
        "contract", "signed", "deal", "acquired", "trade"
    ])
    inj_str = f" ({inj})" if inj and not hide_inj else ""
    
    # Имя, фамилия и амплуа ВСЕГДА идут первыми
    prefix = f"{player} ({pos}){inj_str}"
    event_type = "unknown"

    # ==================== 1. ОБМЕНЫ (TRADES) ====================
    if "acquired" in low and ("from" in low or "for" in low):
        event_type = "trade"
        t_match = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?acquired\s+(.+?)\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)\s+for\s+(.+?)[\.\s$]", clean, re.I)
        if t_match:
            acq_raw, got_raw, from_raw, for_raw = t_match.groups()
            
            # Определяем полные названия клубов
            acq_team = team
            from_team = "клуба соперника"
            for k, full in TEAMS_CLEAN.items():
                if k in acq_raw.lower():
                    acq_team = full
                if k in from_raw.lower():
                    from_team = full

            got_clean = clean_trade_assets(got_raw)
            for_clean = clean_trade_assets(for_raw)

            # Если игрок входит в число приобретенных
            if player.lower() in got_raw.lower():
                team = acq_team
                emoji, act = "🔄", f"выменян у {from_team} в обмен на {for_clean}"
            # Если игрок отдан в обмен
            else:
                team = from_team
                emoji, act = "🔄", f"обменян в {acq_team} на {got_clean}"
        else:
            emoji, act = "🔄", "стал участником обмена"

    # ==================== 2. ПОДПИСАНИЯ КОНТРАКТОВ (SIGNINGS) ====================
    elif any(k in low for k in ["contract", "deal", "extension", "signed"]) and "claim" not in low:
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

    # ==================== 3. ДРАФТ ОТКАЗОВ (WAIVERS) ====================
    elif "claimed" in low and "waiver" in low:
        event_type = "waiver_claimed"
        claim_match = re.search(r"claimed\s+(.+?)\s+off (?:of )?waivers from\s+(.+?)[\.\s]", clean, re.I)
        if claim_match:
            who, from_c = claim_match.groups()
            return f"{team}\n📋 Забрали с драфта отказов у «{from_c.strip()}» {who.strip()} ({pos})"
        emoji, act = "📋", "забран с драфта отказов"
    elif "unconditional waivers" in low:
        event_type, emoji, act = "waiver_unconditional", "❌", "выставлен на драфт отказов для расторжения контракта"
    elif "placed on waivers" in low:
        event_type, emoji, act = "waiver_placed", "⚠️", "выставлен на драфт отказов (waivers)"

    # ==================== 4. СПИСКИ ТРАВМИРОВАННЫХ (IR) ====================
    elif "activated from ir" in low or "activated from injured reserve" in low:
        event_type, emoji, act = "ir_activated", "✅", "активирован из списка травмированных"
    elif "placed on ir" in low or ("placed" in low and "injured reserve" in low):
        event_type, emoji, act = "ir_placed", "🚫", "внесен в список травмированных"

    # ==================== 5. ФАРМ-КЛУБЫ (AHL) ====================
    elif "recalled" in low:
        event_type = "recalled"
        farm_match = re.search(r"from\s+(?:the\s+)?(.+?)(?:\s*\(AHL\))?[\.\s]", clean)
        farm = farm_match.group(1).strip() if farm_match else "фарм-клуба"
        emoji, act = "🚀", f"вызван из {farm} (AHL)"
    elif any(k in low for k in ["assigned", "loaned", "reassigned"]):
        event_type = "assigned"
        dest_match = re.search(r"(?:to|at)\s+(?:the\s+)?(.+?)(?:\s*\((?:AHL|OHL)\))?[\.\s]", clean)
        dest = dest_match.group(1).strip() if dest_match else "фарм-клуб"
        league = "AHL" if "ahl" in low or "assigned" in low else "фарм-клуб"
        emoji, act = "⬇️", f"отправлен в {dest} ({league})"

    # ==================== 6. ВРАТАРИ ====================
    elif any(x in low for x in ["led the", "first goalie off", "warmup"]):
        event_type, emoji, act = "goalie_probable", "🥅", "вероятно будет стартовым вратарем"
    elif "goalie" in pos_en.lower() and ("start" in low or "onto the ice" in low):
        event_type, emoji, act = "goalie_starter", "🥅", f"станет основным вратарем{when_where}"

    # ==================== 7. РЕШЕНИЕ ПЕРЕД МАТЧЕМ (GTD) ====================
    elif "game-time decision" in low or "game time decision" in low:
        event_type = "gtd"
        day_opp = f" {day}{opp_str}".strip() if day else opp_str.strip()
        match_str = f" перед матчем {day_opp}" if day_opp else " перед игрой"
        emoji, act = "🤔", f"Решение по участию будет принято{match_str}"

    # ==================== 8. ТРАВМЫ И СРОКИ ====================
    elif "left" in low and "game" in low and "did not return" in low:
        event_type = "left_game"
        day_str = f" {day}" if day else ""
        emoji, act = "🚑", f"получил повреждение{day_str} и досрочно покинул площадку"
    elif "week-to-week" in low:
        event_type, emoji, act = "week_to_week", "⚠️", "выбыл на несколько недель (статус week-to-week)"
    elif "out for" in low:
        event_type = "out_for"
        m = re.search(r"out for (?:at least )?(?:the next )?(\d+[\-\d]*\s*(?:days|weeks|months))", low)
        period = m.group(1).replace("days", "дней").replace("weeks", "недель").replace("months", "месяцев") if m else "неопределенный срок"
        emoji, act = "⚠️", f"пропустит как минимум {period}"

    # ==================== 9. ТРЕНИРОВКИ И РАСКАТКИ ====================
    elif "non-contact jersey" in low:
        event_type, emoji, act = "practice_noncontact", "🟡", f"тренировался в бесконтактном свитере{f' {day}' if day else ''}"
    elif "full participant" in low or "regular jersey" in low:
        event_type, emoji, act = "practice_full", "🟢", f"тренировался в общей группе без ограничений{f' {day}' if day else ''}"
    elif "missed" in low and "morning skate" in low:
        event_type, emoji, act = "missed_skate", "➖", f"пропустил утреннюю раскатку{f' {day}' if day else ''}"
    elif "missed" in low and "practice" in low:
        event_type, emoji, act = "missed_practice", "➖", f"пропустил тренировку{f' {day}' if day else ''}"

    # ==================== 10. ВЫЕЗДЫ И ВОЗВРАЩЕНИЕ ====================
    elif "will travel" in low and "road trip" in low:
        event_type, emoji, act = "travel_trip", "✈️", "отправится с командой на предстоящую выездную серию"
    elif "chance to return" in low or "could return" in low:
        event_type = "chance_return"
        target = "к концу недели" if "end of the week" in low else (when_where.strip() if when_where else "в ближайшее время")
        emoji, act = "⏳", f"может вернуться в строй {target}"

    # ==================== 11. ДЕБЮТЫ ====================
    elif "season debut" in low:
        event_type, emoji, act = "season_debut", "⭐️", f"проведёт свой первый матч в сезоне{when_where}"
    elif "debut" in low:
        event_type = "debut"
        if "nhl debut" in low:
            emoji, act = "⭐️", f"проведёт свой дебютный матч в карьере в НХЛ{when_where}"
        else:
            emoji, act = "⭐️", f"проведёт свой дебютный матч за клуб{when_where}"

    # ==================== 12. ЗВЕНЬЯ / ЗАПАС / ВОЗВРАЩЕНИЕ ====================
    elif "scratch" in low:
        event_type, emoji, act = "scratch", "❌", f"останется в запасе{when_where}"
    elif any(k in low for k in ["draw back into", "return to the lineup", "re-enter the lineup", "enter the lineup", "draw into", "draw in"]):
        event_type, emoji, act = "lineup_return", "🟢", f"возвращается в состав{when_where}"
    elif ("will play" in low or ("in the" in low and "lineup" in low)) and "will not play" not in low:
        event_type, emoji, act = "will_play", "✅", f"сыграет{when_where}"

    # ==================== 13. НЕ СЫГРАЕТ / OUT / DAY-TO-DAY ====================
    elif any(k in low for k in ["remain out", "is out", "will not play", "ruled out"]):
        event_type = "out"
        dt = " (day-to-day)" if "day-to-day" in low else ""
        emoji, act = "⛔", f"не сыграет{when_where}{dt}"
    elif "day-to-day" in low:
        event_type, emoji, act = "day_to_day", "🚫", "статус day-to-day"

    # ==================== 14. РЕЗЕРВНЫЙ ФОРМАТ ====================
    else:
        event_type, emoji, act = "fallback", "ℹ️", clean

    # ==================== ПРОВЕРКА НА ДУБЛИ ====================
    if check_duplicates:
        dedup_key = f"{player.strip().lower()}:{event_type}"
        if dedup_key in SEEN_EVENTS:
            return None
        SEEN_EVENTS.add(dedup_key)

    return f"{team}\n{emoji} {prefix} {act}"
