import os
import re
import html
from typing import Optional, Set, List, Dict, Any

# Безопасная подгрузка ключа из .env (если файл существует локально)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Подключение OpenAI клиента для редких нетипичных формулировок
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

# 2. Полные названия клубов НХЛ и алиасы (для обменов и драфта отказов)
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
    "wrist": "травма запястья", "hand": "травма кисти", "calf": "травма икроножной мышцы", "leg": "травма ноги",
    "fractured skull": "перелом черепа", "skull fracture": "перелом черепа", "maintenance": "плановый отдых"
}

# 5. Числительные словами для контрактов
NUM_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8
}

CATEGORY_HEADERS = {
    "injury", "line change", "goalie start", "send down", "call up", 
    "trade", "signing", "waiver move", "roster moves", "source:"
}

SEEN_EVENTS: Set[str] = set()

OPENAI_KEY = os.getenv("OPENAI_API_KEY")
ai_client = OpenAI(api_key=OPENAI_KEY) if (OpenAI and OPENAI_KEY) else None

AI_SYSTEM_PROMPT = """
Ты — строгий редактор русскоязычного Telegram-канала о хоккее и НХЛ.
Тебе дан ТОЛЬКО краткий заголовок новости на английском (1 предложение). Твоя задача — вернуть СТРОГО 2 строки:

Строка 1: Полное название команды игрока на английском (строго то, что передано в поле Команда игрока)
Строка 2: {Эмодзи} Имя Фамилия (Амплуа на англ: D, C, LW, RW, G) {суть события на русском языке}

Допустимые форматы для строки 2:
- ❌ Запас: останется в запасе [в день]
- 🟢 Состав: возвращается в состав [в день]
- ⭐️ Дебют: проведёт свой дебютный матч в карьере в НХЛ [в день]
- 🥅 Вратари: станет основным вратарем [в день] ИЛИ вероятно будет стартовым вратарем [в день]
- 🚫 Список травмированных: внесен в список травмированных (IR) ИЛИ внесен в долгосрочный список травмированных (LTIR)
- ✅ Возвращение / готов играть: активирован из списка травмированных и сыграет [в день]
- 🚑 Травма в игре: получил повреждение [в день] и досрочно покинул площадку
- ⛔ Травма: не сыграет [в день]
- 🚀 Фарм: вызван из [Клуб] (AHL)
- ⬇️ Фарм: отправлен в [Клуб] (AHL)

ВАЖНО:
1. НИКОГДА не пиши, против кого играет команда (никаких "против ...").
2. Команда в строке 1 ДОЛЖНА БЫТЬ строго командой самого игрока.
3. Имя хоккеиста и амплуа ВСЕГДА идут первыми в строке 2 сразу после эмодзи!
4. Если в тексте нет конкретного события, верни ровно одно слово: SKIP
"""

def ai_format_or_filter(player: str, pos: str, team: str, clean_headline: str) -> Optional[str]:
    """Нейросеть видит ТОЛЬКО одну строчку заголовка без соперников и воды"""
    if not ai_client:
        return None

    try:
        user_msg = f"Игрок: {player} ({pos})\nКоманда игрока: {team}\nЗаголовок:\n{clean_headline}"
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.1,
            max_tokens=100
        )
        res = response.choices[0].message.content.strip()
        if "SKIP" in res or res == "SKIP":
            return None
        lines = [l.strip() for l in res.split("\n") if l.strip()]
        if len(lines) >= 2:
            team_line = html.escape(lines[0], quote=False)
            body_line = html.escape(lines[1], quote=False)
            return f"<b>{team_line}</b>\n{body_line}"
        return None
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
    """Определяет день недели строго из заголовка"""
    for en, ru in DAYS_MAP.items():
        if re.search(rf"\b{en}\b", text, re.I):
            return ru
    return ""

def get_injury_type(text: str) -> str:
    """Определяет характер травмы строго из заголовка"""
    lower = text.lower()
    for en, ru in INJURIES_MAP.items():
        if en in lower:
            return ru
    return ""

def extract_farm_team(text: str, action: str = "from") -> str:
    """Точно извлекает полное название фарм-клуба"""
    if action == "from":
        m = re.search(r"from\s+(?:the\s+)?([A-Za-z0-9\s\.\/\-]+?)(?:\s*\((?:AHL|ECHL|OHL|WHL)\)|[\.\n$])", text, re.I)
    else:
        m = re.search(r"(?:to|at|report to|sent down to)\s+(?:the\s+)?([A-Za-z0-9\s\.\/\-]+?)(?:\s*\((?:AHL|ECHL|OHL|WHL)\)|[\.\n$])", text, re.I)
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

def extract_only_bold_line(text: str) -> str:
    """
    ЖЕСТКОЕ ПРАВИЛО:
    Берёт ИСКЛЮЧИТЕЛЬНО жирный заголовок новости.
    """
    norm = text.replace("’", "'").replace("`", "'")
    
    span_match = re.search(r'<[^>]*class="[^"]*font-bold[^"]*"[^>]*>(.*?)</[^>]+>', norm, re.I | re.S)
    if span_match:
        return re.sub(r'<[^>]+>', '', span_match.group(1)).strip()
    
    lines = [line.strip() for line in norm.strip().split("\n") if line.strip()]
    
    headline = ""
    for line in lines:
        clean_line = line.strip().rstrip(".,")
        if clean_line.lower() in CATEGORY_HEADERS:
            continue
        headline = line
        break
        
    if not headline:
        headline = lines[0] if lines else norm.strip()
        
    sentence_match = re.split(r'\.\s+', headline)
    if sentence_match and len(sentence_match[0].split()) >= 3:
        return sentence_match[0].strip().rstrip(".") + "."
        
    return headline

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
    Формирует лаконичный пост в едином формате:
    <b>Команда</b>
    {Эмодзи} {Игрок} ({Амплуа}){Травма} {Текст}
    """
    emoji: str = ""
    act: str = ""
    event_type: str = "unknown"

    # Защита от случайного попадания "( G ) | " или "SEA" в название команды
    if "|" in team:
        team = team.split("|")[-1]
    team = re.sub(r"\s+[A-Z]{2,4}$", "", team.strip(" |•-")).strip()

    pos = SHORT_POSITIONS.get(pos_en, "F")
    is_goalie = (pos == "G" or "goalie" in pos_en.lower() or category == "Goalie Start")
    
    clean = extract_only_bold_line(text)
    low = clean.lower()
    
    day = get_day(clean)
    day_str = f" {day}" if day else ""

    # Скрытие травмы для позитивных статусов
    inj = get_injury_type(clean)
    hide_inj = any(k in low for k in [
        "regular jersey", "full participant", "season debut", "will play", 
        "in the lineup", "non-contact", "draw into", "draw back", 
        "return to the lineup", "will return", "expected to return", "set to return",
        "returns vs", "returns on", "scratch", "recalled", "assigned", "loaned", "reassigned",
        "contract", "signed", "deal", "acquired", "trade", "waiver", "claimed", 
        "start", "crease", "debut", "sent down"
    ])
    inj_str = f" ({inj})" if inj and not hide_inj else ""
    prefix = f"{player} ({pos}){inj_str}"

    # ==================== 1. ШАНС НА ВОЗВРАЩЕНИЕ ====================
    if "chance to return" in low or "could return" in low:
        event_type = "chance_return"
        target = "к концу недели" if "end of the week" in low else (day if day else "в ближайшее время")
        emoji, act = "⏳", f"может вернуться в строй {target}"

    # ==================== 2. ТРАВМЫ ВО ВРЕМЯ МАТЧА ====================
    elif any(k in low for k in ["left", "leaves", "exited", "exits"]) and any(g in low for g in ["game", "ice", "match"]):
        event_type = "left_game"
        emoji, act = "🚑", f"получил повреждение{day_str} и досрочно покинул площадку"

    # ==================== 3. ЗВЕНЬЯ: ЗАПАС ИЛИ ВОЗВРАЩЕНИЕ В СОСТАВ ====================
    elif "scratch" in low or "press box" in low:
        event_type, emoji, act = "scratch", "❌", f"останется в запасе{day_str}"

    elif any(k in low for k in [
        "draw back into", "return to the lineup", "re-enter the lineup", 
        "enter the lineup", "draw into", "draw in", "back in",
        "will return", "expected to return", "set to return", "likely to return", "returns vs", "returns on"
    ]):
        event_type, emoji, act = "lineup_return", "🟢", f"возвращается в состав{day_str}"

    elif ("will play" in low or ("in the" in low and "lineup" in low)) and "will not play" not in low:
        event_type, emoji, act = "will_play", "✅", f"сыграет{day_str}"

    # ==================== 4. СТАРТОВЫЕ ВРАТАРИ ====================
    elif is_goalie and (category == "Goalie Start" or any(k in low for k in ["start", "crease", "in net", "pipes", "warmup", "skate", "ice", "off", "first"])):
        if any(x in low for x in [
            "starter's crease", "starter crease", "morning skate", "warmup", "first goalie off", "led the"
        ]):
            event_type, emoji, act = "goalie_probable", "🥅", f"вероятно будет стартовым вратарем{day_str}"
        elif any(x in low for x in [
            "start", "starting", "in net", "between the pipes", "return to the crease", 
            "returns to the crease", "in the crease", "gets the nod"
        ]):
            event_type, emoji, act = "goalie_starter", "🥅", f"станет основным вратарем{day_str}"
        elif category == "Goalie Start":
            event_type, emoji, act = "goalie_probable", "🥅", f"вероятно будет стартовым вратарем{day_str}"

    # ==================== 5. ВОЗВРАЩЕНИЕ ИЗ ТРАВМЫ / АКТИВАЦИЯ ИЗ IR ====================
    elif "activated from ir" in low or "activated from injured reserve" in low:
        if any(k in low for k in ["assigned", "loaned", "reassigned", "sent down"]):
            event_type = "ir_activated_assigned"
            dest = extract_farm_team(clean, action="to")
            emoji, act = "✅", f"активирован из списка травмированных и отправлен в {dest} (AHL)"
        elif "will play" in low or "play" in low:
            event_type = "ir_activated_play"
            emoji, act = "✅", f"активирован из списка травмированных и сыграет{day_str}"
        else:
            event_type = "ir_activated"
            emoji, act = "✅", f"активирован из списка травмированных{day_str}"

    # ==================== 6. СРОКИ ТРАВМЫ ====================
    elif any(k in low for k in ["will miss", "out for"]):
        m = re.search(r"(?:will miss|out for)\s+(?:at least\s+)?(?:the next\s+)?(\d+[\-\d\s]*(?:to\s+\d+\s*)?(?:days|weeks|months))", low)
        if m:
            period = m.group(1).replace("days", "дней").replace("weeks", "недель").replace("months", "месяцев").replace("to", "–")
            event_type = "injury_miss_period"
            emoji, act = "⚠️", f"пропустит {period}"
        elif "week-to-week" in low:
            event_type, emoji, act = "week_to_week", "⚠️", "выбыл на несколько недель (статус week-to-week)"

    # ==================== 7. СПИСОК ТРАВМИРОВАННЫХ (IR / LTIR) ====================
    elif any(k in low for k in ["placed on ir", "placed on ltir", "moved to ltir", "moved to long-term injured reserve", "placed on injured reserve", "on injured reserve", "to ltir"]):
        if "ltir" in low or "long-term" in low:
            event_type, emoji, act = "ir_placed", "🚫", f"внесен в долгосрочный список травмированных (LTIR){day_str}"
        else:
            event_type, emoji, act = "ir_placed", "🚫", f"внесен в список травмированных{day_str}"

    # ==================== 8. ДЕБЮТ В НХЛ / СЕЗОНЕ ====================
    elif "debut" in low:
        if "nhl debut" in low:
            event_type, emoji, act = "nhl_debut", "⭐️", f"проведёт свой дебютный матч в карьере в НХЛ{day_str}"
        elif "season debut" in low:
            event_type, emoji, act = "season_debut", "⭐️", f"проведёт свой первый матч в сезоне{day_str}"
        else:
            event_type, emoji, act = "club_debut", "⭐️", f"проведёт свой дебютный матч за клуб{day_str}"

    # ==================== 9. ВЫЗОВЫ И ССЫЛКИ В АХЛ ====================
    elif "recalled" in low or "called up" in low:
        event_type = "recalled"
        farm = extract_farm_team(clean, action="from")
        emoji, act = "🚀", f"вызван из {farm} (AHL)"

    elif any(k in low for k in ["assigned", "loaned", "reassigned", "sent down"]):
        event_type = "assigned"
        dest = extract_farm_team(clean, action="to")
        emoji, act = "⬇️", f"отправлен в {dest} (AHL)"

    # ==================== 10. ДРАФТ ОТКАЗОВ (WAIVERS) ====================
    elif category == "Waiver Move" or any(k in low for k in ["waiver", "waivers"]):
        claim_match_direct = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?(?:claimed|acquired)\s+(.+?)\s+off\s+(?:of\s+)?waivers\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)[\.\s$]", clean, re.I)
        claim_match_inv = re.search(r"([a-z\s\.\-]+?)\s+(?:has\s+)?claimed\s+(.+?)\s+from\s+(?:the\s+)?([a-z\s\.\-]+?)\s+(?:off\s+(?:of\s+)?waivers|on\s+[a-z]+)[\.\s$]", clean, re.I)

        if claim_match_direct or claim_match_inv:
            m = claim_match_direct if claim_match_direct else claim_match_inv
            who_claimed_raw, who_got, from_c_raw = m.groups()
            for k, full in TEAMS_CLEAN.items():
                if k in who_claimed_raw.lower():
                    team = full
                if k in from_c_raw.lower():
                    from_c_raw = full
            event_type = f"waiver_claim:{from_c_raw.lower()}:{team.lower()}"
            emoji, act = "📋", f"забран с драфта отказов у «{from_c_raw.strip()}»{day_str}"
        elif "unconditional waivers" in low or "contract termination" in low:
            event_type = "waiver_unconditional"
            emoji, act = "❌", f"выставлен на драфт отказов для расторжения контракта{day_str}"
        elif "cleared waivers" in low:
            event_type = "cleared_assigned"
            dest = extract_farm_team(clean, action="to")
            emoji, act = "⬇️", f"прошёл драфт отказов и отправлен в {dest} (AHL)"
        elif "placed on waivers" in low or "placing" in low and "waivers" in low:
            event_type = "waiver_placed"
            emoji, act = "⚠️", f"выставлен на драфт отказов (waivers){day_str}"

    # ==================== 11. ОБМЕНЫ (TRADES) ====================
    elif "acquired" in low and ("from" in low or "for" in low):
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

    # ==================== 12. ПОДПИСАНИЯ КОНТРАКТОВ (SIGNINGS) ====================
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

    # ==================== 13. РЕШЕНИЕ ПЕРЕД МАТЧЕМ (GTD) ====================
    elif any(k in low for k in ["game-time decision", "game time decision", "questionable", "doubtful", "up in the air"]):
        event_type = "gtd"
        match_str = f" перед матчем{day_str}" if day else " перед игрой"
        emoji, act = "🤔", f"Решение по участию будет принято{match_str}"

    # ==================== 14. НЕ СЫГРАЕТ / OUT / DAY-TO-DAY ====================
    elif any(k in low for k in ["remain out", "is out", "will not play", "ruled out", "sidelined with"]):
        event_type = "out"
        dt = " (day-to-day)" if "day-to-day" in low else ""
        emoji, act = "⛔", f"не сыграет{day_str}{dt}"
    elif "day-to-day" in low:
        event_type, emoji, act = "day_to_day", "🚫", "статус day-to-day"

    # ==================== 15. ТРЕНИРОВКИ ====================
    elif "non-contact jersey" in low:
        event_type, emoji, act = "practice_noncontact", "🟡", f"тренировался в бесконтактном свитере{day_str}"
    elif "full participant" in low or "regular jersey" in low:
        event_type, emoji, act = "practice_full", "🟢", f"тренировался в общей группе без ограничений{day_str}"
    elif "missed" in low and "morning skate" in low:
        event_type, emoji, act = "missed_skate", "➖", f"пропустил утреннюю раскатку{day_str}"
    elif "missed" in low and "practice" in low:
        event_type, emoji, act = "missed_practice", "➖", f"пропустил тренировку{day_str}"

    # ==================== 16. ВЫЕЗДЫ С КОМАНДОЙ ====================
    elif "will travel" in low and "road trip" in low:
        event_type, emoji, act = "travel_trip", "✈️", "отправится с командой на предстоящую выездную серию"

    # ==================== 17. СТРОГИЙ AI ====================
    if not emoji or not act or event_type == "unknown":
        ai_post = ai_format_or_filter(player, pos, team, clean)
        if ai_post:
            return ai_post
        return None

    # ==================== ПРОВЕРКА НА ДУБЛИ ====================
    if check_duplicates:
        if event_type == "trade" and "acq_team" in locals() and "from_team" in locals():
            clubs = sorted([acq_team.lower(), from_team.lower()])
            dedup_key = f"trade:{clubs[0]}:{clubs[1]}"
        else:
            dedup_key = f"{player.strip().lower()}:{event_type}"

        if dedup_key in SEEN_EVENTS:
            return None
        SEEN_EVENTS.add(dedup_key)

    safe_team = html.escape(team, quote=False)
    safe_prefix = html.escape(prefix, quote=False)
    safe_act = html.escape(act, quote=False)

    return f"<b>{safe_team}</b>\n{emoji} {safe_prefix} {safe_act}"
