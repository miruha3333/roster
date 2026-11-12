import re

# 1. Лаконичные обозначения позиций
SHORT_POSITIONS = {
    "Defenseman": "D", "defense": "D", "d": "D",
    "Center": "C", "c": "C",
    "Left Wing": "LW", "left wing": "LW", "lw": "LW",
    "Right Wing": "RW", "right wing": "RW", "rw": "RW",
    "Forward": "F", "forward": "F", "f": "F",
    "Goalie": "G", "goalie": "G", "g": "G"
}

# 2. Полные названия клубов НХЛ
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

def get_day(text: str) -> str:
    """Определяет день недели из текста"""
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

def build_telegram_post(player: str, pos_en: str, team: str, category: str, text: str, source: str = "") -> str:
    """
    Генерирует лаконичные посты строго по единому формату:
    {Команда}
    {Эмодзи} {Игрок} ({Амплуа}){Травма} {Действие / Соперник / Дата}
    """
    pos = SHORT_POSITIONS.get(pos_en, "F")
    clean = text.strip()
    low = clean.lower()
    day = get_day(clean)
    opp = get_opponent(clean)

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

    # Определение травмы: скрываем её, если игрок уже играет / вернулся / здоров в запасе
    inj = get_injury_type(clean)
    hide_inj = any(k in low for k in [
        "regular jersey", "full participant", "season debut", "will play", 
        "in the lineup", "non-contact", "draw into", "draw back", 
        "return to the lineup", "scratch", "recalled", "assigned", "loaned"
    ])
    inj_str = f" ({inj})" if inj and not hide_inj else ""
    
    # Единый префикс: Имя, Фамилия, Амплуа и Травма (если есть) всегда первыми!
    prefix = f"{player} ({pos}){inj_str}"

    # ==================== 1. ОБМЕНЫ (TRADE) ====================
    if "acquired" in low and "from" in low and "for" in low:
        trade_match = re.search(r"acquired\s+(.+?)\s+from\s+(.+?)\s+for\s+(.+?)[\.\s]", clean, re.I)
        if trade_match:
            got_player, from_club, gave_away = trade_match.groups()
            for key, full_team in TEAMS_CLEAN.items():
                if key in from_club.lower():
                    from_club = full_team
                    break
            return f"{team}\n🔄 Обменяли {gave_away.strip()} в {from_club.strip()} на {got_player.strip()}"

    # ==================== 2. ДРАФТ ОТКАЗОВ (WAIVERS) ====================
    if "claimed" in low and "waiver" in low:
        claim_match = re.search(r"claimed\s+(.+?)\s+off (?:of )?waivers from\s+(.+?)[\.\s]", clean, re.I)
        if claim_match:
            who, from_c = claim_match.groups()
            return f"{team}\n📋 Забрали с драфта отказов у «{from_c.strip()}» {who.strip()} ({pos})"
        return f"{team}\n📋 {prefix} забран с драфта отказов"
    if "unconditional waivers" in low:
        emoji, act = "❌", "выставлен на драфт отказов для расторжения контракта"
    elif "placed on waivers" in low:
        emoji, act = "⚠️", "выставлен на драфт отказов (waivers)"

    # ==================== 3. КОНТРАКТЫ (SIGNINGS) ====================
    elif "contract" in low or "extension" in low:
        c_match = re.search(r"(\d+)-year[^\$]*(\$[\d,]+(?:\.\d+)?(?:M|K)?)", clean, re.I)
        if c_match:
            years, money = c_match.groups()
            emoji, act = "✍️", f"подписал контракт на {years} г. ({money})"
        else:
            emoji, act = "✍️", "подписал новое соглашение с клубом"

    # ==================== 4. СПИСКИ ТРАВМИРОВАННЫХ (IR) ====================
    elif "activated from ir" in low or "activated from injured reserve" in low:
        emoji, act = "✅", "активирован из списка травмированных"
    elif "placed on ir" in low or ("placed" in low and "injured reserve" in low):
        emoji, act = "🚫", "внесен в список травмированных"

    # ==================== 5. ФАРМ-КЛУБЫ (AHL / ВЫЗОВЫ И ОТПРАВКИ) ====================
    elif "recalled" in low:
        farm_match = re.search(r"from\s+(?:the\s+)?(.+?)(?:\s*\(AHL\))?[\.\s]", clean)
        farm = farm_match.group(1).strip() if farm_match else "фарм-клуба"
        emoji, act = "🚀", f"вызван из {farm} (AHL)"
    elif any(k in low for k in ["assigned", "loaned", "reassigned"]):
        dest_match = re.search(r"(?:to|at)\s+(?:the\s+)?(.+?)(?:\s*\((?:AHL|OHL)\))?[\.\s]", clean)
        dest = dest_match.group(1).strip() if dest_match else "фарм-клуб"
        league = "AHL" if "ahl" in low or "assigned" in low else "фарм-клуб"
        emoji, act = "⬇️", f"отправлен в {dest} ({league})"

    # ==================== 6. СТАРТОВЫЕ ВРАТАРИ ====================
    elif any(x in low for x in ["led the", "first goalie off", "warmup"]):
        emoji, act = "🥅", "вероятно будет стартовым вратарем"
    elif "goalie" in pos_en.lower() and ("start" in low or "onto the ice" in low):
        emoji, act = "🥅", f"станет основным вратарем{when_where}"

    # ==================== 7. РЕШЕНИЕ ПЕРЕД МАТЧЕМ (GAME-TIME DECISION) ====================
    elif "game-time decision" in low or "game time decision" in low:
        day_opp = f" {day}{opp_str}".strip() if day else opp_str.strip()
        match_str = f" перед матчем {day_opp}" if day_opp else " перед игрой"
        emoji, act = "🤔", f"Решение по участию будет принято{match_str}"

    # ==================== 8. ТРАВМА В ИГРЕ И СРОКИ ВЫБЫВАНИЯ ====================
    elif "left" in low and "game" in low and "did not return" in low:
        day_str = f" {day}" if day else ""
        emoji, act = "🚑", f"получил повреждение{day_str} и досрочно покинул площадку"
    elif "week-to-week" in low:
        emoji, act = "⚠️", "выбыл на несколько недель (статус week-to-week)"
    elif "out for" in low:
        m = re.search(r"out for (?:at least )?(?:the next )?(\d+[\-\d]*\s*(?:days|weeks|months))", low)
        period = m.group(1).replace("days", "дней").replace("weeks", "недель").replace("months", "месяцев") if m else "неопределенный срок"
        emoji, act = "⚠️", f"пропустит как минимум {period}"

    # ==================== 9. ТРЕНИРОВКИ И РАСКАТКИ ====================
    elif "non-contact jersey" in low:
        day_str = f" {day}" if day else ""
        emoji, act = "🟡", f"тренировался в бесконтактном свитере{day_str}"
    elif "full participant" in low or "regular jersey" in low:
        day_str = f" {day}" if day else ""
        emoji, act = "🟢", f"тренировался в общей группе без ограничений{day_str}"
    elif "missed" in low and "morning skate" in low:
        day_str = f" {day}" if day else ""
        emoji, act = "➖", f"пропустил утреннюю раскатку{day_str}"
    elif "missed" in low and "practice" in low:
        day_str = f" {day}" if day else ""
        emoji, act = "➖", f"пропустил тренировку{day_str}"

    # ==================== 10. ВЫЕЗДЫ И ВОЗМОЖНОЕ ВОЗВРАЩЕНИЕ ====================
    elif "will travel" in low and "road trip" in low:
        emoji, act = "✈️", "отправится с командой на предстоящую выездную серию"
    elif "chance to return" in low or "could return" in low:
        if "end of the week" in low:
            target = "к концу недели"
        elif when_where:
            target = when_where.strip()
        else:
            target = "в ближайшее время"
        emoji, act = "⏳", f"может вернуться в строй {target}"

    # ==================== 11. ДЕБЮТЫ ====================
    elif "season debut" in low:
        emoji, act = "⭐️", f"проведёт свой первый матч в сезоне{when_where}"
    elif "debut" in low:
        if "nhl debut" in low:
            emoji, act = "⭐️", f"проведёт свой дебютный матч в карьере в НХЛ{when_where}"
        else:
            emoji, act = "⭐️", f"проведёт свой дебютный матч за клуб{when_where}"

    # ==================== 12. ИЗМЕНЕНИЯ В СОСТАВЕ (ЗВЕНЬЯ / ВЕРНУЛСЯ / ЗАПАС) ====================
    elif "scratch" in low:
        emoji, act = "❌", f"останется в запасе{when_where}"
    elif any(k in low for k in ["draw back into", "return to the lineup", "re-enter the lineup", "enter the lineup", "draw into", "draw in"]):
        emoji, act = "🟢", f"возвращается в состав{when_where}"
    elif ("will play" in low or ("in the" in low and "lineup" in low)) and "will not play" not in low:
        emoji, act = "✅", f"сыграет{when_where}"

    # ==================== 13. НЕ СЫГРАЕТ / ТРАВМА / DAY-TO-DAY ====================
    elif any(k in low for k in ["remain out", "is out", "will not play", "ruled out"]):
        dt = " (day-to-day)" if "day-to-day" in low else ""
        emoji, act = "⛔", f"не сыграет{when_where}{dt}"
    elif "day-to-day" in low:
        emoji, act = "🚫", "статус day-to-day"

    # ==================== 14. РЕЗЕРВНЫЙ ФОРМАТ ====================
    else:
        emoji, act = "ℹ️", clean

    # ИТОГОВЫЙ СТРОГИЙ ВЫВОД
    return f"{team}\n{emoji} {prefix} {act}"
