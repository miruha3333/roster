import re

# Краткие латинские обозначения позиций, как в ваших примерах: (D), (C), (LW), (RW), (G)
SHORT_POSITIONS = {
    "Defenseman": "D", "defense": "D", "d": "D",
    "Center": "C", "c": "C",
    "Left Wing": "LW", "left wing": "LW", "lw": "LW",
    "Right Wing": "RW", "right wing": "RW", "rw": "RW",
    "Forward": "F", "forward": "F", "f": "F",
    "Goalie": "G", "goalie": "G", "g": "G"
}

# Словарь для перевода названий клубов соперников на полный вид
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
    "rangers": "New York Rangers", "ny rangers": "New York Rangers",
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

DAYS_MAP = {
    "sunday": "в воскресенье", "monday": "в понедельник", "tuesday": "во вторник",
    "wednesday": "в среду", "thursday": "в четверг", "friday": "в пятницу",
    "saturday": "в субботу", "today": "сегодня", "tonight": "сегодня ночью"
}

INJURIES_MAP = {
    "upper-body": "верхняя часть тела", "upper body": "верхняя часть тела",
    "lower-body": "нижняя часть тела", "lower body": "нижняя часть тела",
    "undisclosed": "не раскрывается", "illness": "болезнь",
    "knee": "колено", "hip": "бедро", "groin": "пах", "shoulder": "плечо"
}

def get_day(text: str) -> str:
    """Определяет день недели из текста"""
    lower = text.lower()
    for en, ru in DAYS_MAP.items():
        if re.search(rf"\b{en}\b", lower):
            return ru
    return "в ближайшем матче"

def get_opponent(text: str) -> str:
    """Ищет соперника после предлогов vs., in, against, at"""
    lower = text.lower()
    match = re.search(r"(?:vs\.?|against|in|at)\s+(?:the\s+)?([a-z\s\.\-]+)", lower)
    if match:
        raw_opp = match.group(1).strip().rstrip(".,")
        for key, full_team in TEAMS_CLEAN.items():
            if key in raw_opp:
                return full_team
    return ""

def get_injury_type(text: str) -> str:
    """Определяет характер травмы из скобок (upper-body и т.д.)"""
    lower = text.lower()
    for en, ru in INJURIES_MAP.items():
        if en in lower:
            return ru
    return ""

def build_telegram_post(player: str, pos_en: str, team: str, category: str, text: str, source: str) -> str:
    """
    Генерирует лаконичные посты строго по новому формату
    """
    pos = SHORT_POSITIONS.get(pos_en, "F")
    clean_text = text.strip()
    lower = clean_text.lower()
    day = get_day(clean_text)
    opp = get_opponent(clean_text)

    # 1. ВОЗВРАЩЕНИЕ В СТРОЙ (IR ACTIVATED)
    # Пример: Pavel Mintyukov (D) активирован из списка травмированных
    if "activated from ir" in lower:
        return f"{team}\n✅ {player} ({pos}) активирован из списка травмированных"

    # 2. ПОМЕЩЕНИЕ В СПИСОК ТРАВМИРОВАННЫХ (IR PLACED)
    # Пример: John Marino (D) внесен в список травмированных
    if "placed on ir" in lower or "placed" in lower and "injured reserve" in lower:
        return f"{team}\n🚫 {player} ({pos}) внесен в список травмированных"

    # 3. ОТПРАВКА В ФАРМ-КЛУБ (AHL / JUNIOR)
    # Пример: Nick Jensen (D) отправлен в San Diego (AHL)
    if any(k in lower for k in ["assigned", "loaned", "reassigned"]):
        dest_match = re.search(r"(?:to|at)\s+(?:the\s+)?(.+?)(?:\s*\((?:AHL|OHL)\))?[\.\s]", clean_text)
        dest = dest_match.group(1).strip() if dest_match else "фарм-клуб"
        league = "AHL" if "ahl" in lower or "assigned" in lower else "фарм-клуб"
        return f"{team}\n⬇️ {player} ({pos}) отправлен в {dest} ({league})"

    # 4. ВЫЗОВ ИЗ ФАРМ-КЛУБА
    # Пример: Ben McCartney (LW) вызван из Tucson (AHL)
    if "recalled" in lower:
        farm_match = re.search(r"from\s+(?:the\s+)?(.+?)(?:\s*\(AHL\))?[\.\s]", clean_text)
        farm = farm_match.group(1).strip() if farm_match else "фарм-клуба"
        return f"{team}\n🚀 {player} ({pos}) вызван из {farm} (AHL)"

    # 5. СТАРТОВЫЙ ВРАТАРЬ
    # Пример: Jonas Johansson (G) станет основным вратарем в воскресенье против Anaheim Ducks
    # Пример: Karel Vejmelka (G) вероятно будет стартовым вратарем
    if "goalie" in pos_en.lower() or "start" in lower or "onto the ice" in lower:
        if "led the" in lower or "first goalie off" in lower or "warmup" in lower:
            return f"{team}\n🥅 {player} ({pos}) вероятно будет стартовым вратарем"
        
        opp_str = f" против {opp}" if opp else ""
        return f"{team}\n🥅 {player} ({pos}) станет основным вратарем {day}{opp_str}"

    # 6. ТРЕНИРОВКИ / ПРОПУСК ЗАНЯТИЯ
    # Пример: Matty Beniers (C) пропустил тренировку в воскресенье, но вернется на лед во вторник
    if "missed" in lower and "practice" in lower:
        rejoin_day = "скоро"
        for en, ru in DAYS_MAP.items():
            if f"on {en}" in lower or f"on {en}/" in lower:
                rejoin_day = ru
        return f"{team}\n➖ {player} ({pos}) пропустил тренировку {day}, но вернется на лед {rejoin_day}"

    # 7. ДЕБЮТ В СЕЗОНЕ ИЛИ НХЛ
    # Пример: Scott Morrow (D) проведёт свой первый матч в нынешнем сезоне в основном составе.
    if "debut" in lower:
        if "season debut" in lower:
            return f"{team}\n❕ {player} ({pos}) проведёт свой первый матч в нынешнем сезоне в основном составе"
        return f"{team}\n⭐️ {player} ({pos}) проведёт свой дебютный матч в карьере в НХЛ"

    # 8. НЕ СЫГРАЕТ В МАТЧЕ / DAY-TO-DAY / ТРАВМА
    # Пример: Sean Durzi (D) не сыграет в воскресенье против Edmonton Oilers
    # Пример: Kailer Yamamoto (RW) травма (верхняя часть тела)
    if "will not play" in lower or "is day-to-day" in lower:
        inj_type = get_injury_type(clean_text)
        if "day-to-day" in lower and inj_type:
            return f"{team}\n🚫 {player} ({pos}) травма ({inj_type})"
        
        opp_str = f" против {opp}" if opp else ""
        return f"{team}\n⛔ {player} ({pos}) не сыграет {day}{opp_str}"

    # 9. ОБМЕНЫ (TRADE)
    # Пример: Nashville Predators 🔄 Обменяли Matthew Wood в Seattle Kraken на Shane Wright
    if "acquired" in lower and "from" in lower and "for" in lower:
        trade_match = re.search(r"acquired\s+(.+?)\s+from\s+(.+?)\s+for\s+(.+?)[\.\s]", clean_text, re.IGNORECASE)
        if trade_match:
            got_player, from_club, gave_away = trade_match.groups()
            for key, full_team in TEAMS_CLEAN.items():
                if key in from_club.lower():
                    from_club = full_team
                    break
            return f"{team}\n🔄 Обменяли {gave_away.strip()} в {from_club.strip()} на {got_player.strip()}"

    # 10. ВНЕ СОСТАВА (HEALTHY SCRATCH)
    # Пример: Michael Bunting (LW) останется в запасе
    if "scratched" in lower:
        return f"{team}\n❌ {player} ({pos}) останется в запасе"

    # 11. ДРАФТ ОТКАЗОВ (WAIVER MOVE)
    # Пример: Minnesota Wild 📋 Забрали с драфта отказов Ottawa Cameron Crotty (D)
    if "claimed" in lower and "waiver" in lower:
        claim_match = re.search(r"claimed\s+(.+?)\s+off (?:of )?waivers from\s+(.+?)[\.\s]", clean_text, re.IGNORECASE)
        if claim_match:
            who, from_c = claim_match.groups()
            return f"{team}\n📋 Забрали с драфта отказов у «{from_c.strip()}» {who.strip()} ({pos})"
        return f"{team}\n📋 {player} ({pos}) забран с драфта отказов"

    if "unconditional waivers" in lower:
        return f"{team}\n❌ {player} ({pos}) выставлен на драфт отказов для расторжения контракта"

    if "placed on waivers" in lower:
        return f"{team}\n⚠️ {player} ({pos}) выставлен на драфт отказов (waivers)"

    # 12. ПОДПИСАНИЕ КОНТРАКТА (SIGNING)
    # Пример: Carolina Hurricanes ✍️ Alexander Nikishin (D) подписал контракт на 1 год ($3,000,000)
    if "contract" in lower:
        c_match = re.search(r"(\d+)-year,\s*(\$[\d,]+)", clean_text)
        if c_match:
            years, money = c_match.groups()
            return f"{team}\n✍️ {player} ({pos}) подписал контракт на {years} г. ({money})"
        return f"{team}\n✍️ {player} ({pos}) подписал новое соглашение с клубом"

    # 13. ВОЗВРАЩЕНИЕ В СОСТАВ
    # Пример: Noah Juulsen (D) возвращается в состав в субботу
    if any(k in lower for k in ["enter the lineup", "draw into", "back in the"]):
        return f"{team}\n🟢 {player} ({pos}) возвращается в состав {day}"

    # Резервный компактный формат
    return f"{team}\nℹ️ {player} ({pos}) {clean_text}"
