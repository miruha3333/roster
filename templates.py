import re
from config import POSITIONS, DAYS_TRANSLATE, INJURIES_TRANSLATE

def clean_days(text: str) -> str:
    for en, ru in DAYS_TRANSLATE.items():
        text = re.sub(rf"\b{en}\b", ru, text, flags=re.IGNORECASE)
    return text

def clean_injury(text: str) -> str:
    for en, ru in INJURIES_TRANSLATE.items():
        text = re.sub(rf"\b{en}\b", ru, text, flags=re.IGNORECASE)
    return text

# 1. КОНТРАКТЫ (SIGNING)
def format_signing(player: str, pos: str, team: str, text: str) -> str:
    # Пример: 1-year, $850,000 contract with the New York Rangers. Expires 2027 (UFA).
    contract_match = re.search(r"(\d+)-year,\s*(\$[\d,]+)\s*contract.*?Expires\s*(\d{4})\s*\(([A-Z]+)\)", text, re.IGNORECASE)
    if contract_match:
        years, amount, expires, status = contract_match.groups()
        return (
            f"✍️ <b>НОВЫЙ КОНТРАКТ</b>\n\n"
            f"«{team}» подписали {pos.lower()}а <b>{player}</b>.\n\n"
            f"💰 <b>Срок и сумма:</b> {years} г. / {amount}\n"
            f"⏳ <b>Действует до:</b> {expires} ({status})"
        )
    
    # Пример: The Kings have signed Jared Wright to a two-year contract worth $925K AAV.
    aav_match = re.search(r"signed .+? to a (.+?) contract worth (.+? AAV)", text, re.IGNORECASE)
    if aav_match:
        term, aav = aav_match.groups()
        return (
            f"✍️ <b>НОВЫЙ КОНТРАКТ</b>\n\n"
            f"«{team}» подписали соглашение с <b>{player}</b> ({pos}).\n"
            f"💰 <b>Условия:</b> {term} ({aav})."
        )
    return None

# 2. ОБМЕНЫ (TRADE)
def format_trade(player: str, pos: str, team: str, text: str) -> str:
    # Пример: The Devils have acquired Connor Hellebuyck from the Jets for Dawson Mercer, Nico Daws...
    trade_match = re.search(r"(?:The\s+)?(.+?)\s+have acquired\s+(.+?)\s+from\s+(?:the\s+)?(.+?)\s+for\s+(.+?)(?:\.|$)", text, re.IGNORECASE)
    if trade_match:
        to_team, acquired, from_team, package = trade_match.groups()
        return (
            f"🔄 <b>ОБМЕН В НХЛ</b>\n\n"
            f"«{to_team.strip()}» выменяли у «{from_team.strip()}»:\n"
            f"📥 <b>{acquired.strip()}</b>\n\n"
            f"Взамен в «{from_team.strip()}» отправляются:\n"
            f"📤 <b>{package.strip()}</b>"
        )
    return None

# 3. ДРАФТ ОТКАЗОВ (WAIVER MOVE)
def format_waiver(player: str, pos: str, team: str, text: str) -> str:
    # Забор с драфта отказов: Minnesota has claimed Cameron Crotty off of waivers from Ottawa.
    claim_match = re.search(r"(.+?)\s+has claimed\s+(.+?)\s+off (?:of )?waivers from\s+(.+?)(?:\.|$)", text, re.IGNORECASE)
    if claim_match:
        claimer, who, from_who = claim_match.groups()
        return (
            f"📋 <b>ЗАБОР С ДРАФТА ОТКАЗОВ</b>\n\n"
            f"«{claimer.strip()}» забрали с уэйвера {pos.lower()}а <b>{who.strip()}</b> у «{from_who.strip()}»."
        )

    # Расторжение контракта: is being placed on unconditional waivers for a contract termination
    if "unconditional waivers" in text.lower():
        return (
            f"❌ <b>РАСТОРЖЕНИЕ КОНТРАКТА</b>\n\n"
            f"«{team}» поместили {pos.lower()}а <b>{player}</b> на безусловный драфт отказов с целью расторжения соглашения."
        )

    # Успешный проход уэйвера
    if "cleared waivers" in text.lower():
        return (
            f"✅ <b>ПРОХОЖДЕНИЕ ДРАФТА ОТКАЗОВ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> успешно прошёл процедуру уэйвера и отправляется в фарм-клуб."
        )

    # Выставление на уэйвер
    if "placed" in text.lower() and "on waivers" in text.lower():
        return (
            f"⚠️ <b>ВЫСТАВЛЕН НА ДРАФТ ОТКАЗОВ</b>\n\n"
            f"«{team}» выставили {pos.lower()}а <b>{player}</b> на драфт отказов (waivers)."
        )
    return None

# 4. ДВИЖЕНИЕ МЕЖДУ ЛИГАМИ (CALL UP / SEND DOWN)
def format_roster_move(player: str, pos: str, team: str, text: str, category: str) -> str:
    # Вызов из АХЛ
    if category == "Call Up" or "recalled from" in text.lower():
        farm_match = re.search(r"from (?:the )?(.+?)(?:\s*\(AHL\))?\.", text)
        farm = farm_match.group(1) if farm_match else "АХЛ"
        return (
            f"🚀 <b>ВЫЗОВ ИЗ АХЛ</b>\n\n"
            f"«{team}» вызвали в основную команду {pos.lower()}а <b>{player}</b> из «{farm}»."
        )

    # Ссылка в АХЛ / юниоры
    if category == "Send Down" or "assigned to" in text.lower() or "loaned to" in text.lower() or "reassigned to" in text.lower():
        dest_match = re.search(r"to (?:the )?(.+?)(?:\s*\((?:AHL|OHL)\))?\.", text)
        dest = dest_match.group(1) if dest_match else "фарм-клуб"
        return (
            f"📦 <b>ОТПРАВКА В ФАРМ-КЛУБ</b>\n\n"
            f"«{team}» отправили {pos.lower()}а <b>{player}</b> в команду «{dest}»."
        )
    return None

# 5. ИЗМЕНЕНИЯ В СОСТАВЕ (LINE CHANGE)
def format_line_change(player: str, pos: str, team: str, text: str) -> str:
    text_ru = clean_days(text)

    # Здоровый запас (Healthy Scratch)
    if "scratched" in text.lower():
        return (
            f"🚫 <b>ВНЕ ЗАЯВКИ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> останется в запасе (healthy scratch).\n"
            f"<i>{text_ru}</i>"
        )

    # Дебют в НХЛ
    if "nhl debut" in text.lower():
        return (
            f"⭐️ <b>ДЕБЮТ В НХЛ!</b>\n\n"
            f"Молодой {pos.lower()} «{team}» <b>{player}</b> сегодня проведёт свой первый матч в карьере в НХЛ!"
        )

    # Дебют в сезоне
    if "season debut" in text.lower():
        return (
            f"✨ <b>ДЕБЮТ В СЕЗОНЕ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> проведёт свой первый матч в нынешнем сезоне."
        )

    # Вход в состав
    if any(k in text.lower() for k in ["enter the lineup", "draw into the lineup", "back in the"]):
        return (
            f"🟢 <b>ВОЗВРАЩЕНИЕ В СОСТАВ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> возвращается в заявку команды.\n"
            f"<i>{text_ru}</i>"
        )
    return None

# 6. ТРАВМЫ И ВОССТАНОВЛЕНИЕ (INJURY)
def format_injury(player: str, pos: str, team: str, text: str) -> str:
    text_ru = clean_days(clean_injury(text))

    # Вывод из списка травмированных (IR)
    if "activated from ir" in text.lower():
        return (
            f"💪 <b>ВОЗВРАЩЕНИЕ В СТРОЙ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> активирован из списка травмированных (IR) и готов играть."
        )

    # Помещение в список травмированных (IR)
    if "placed on ir" in text.lower() or "placed on injured reserve" in text.lower():
        return (
            f"🏥 <b>СПИСОК ТРАВМИРОВАННЫХ (IR)</b>\n\n"
            f"«{team}» внесли {pos.lower()}а <b>{player}</b> в лазарет команды (Injured Reserve)."
        )

    # Сроки восстановления (will miss X weeks)
    weeks_match = re.search(r"will miss (.+?)\.", text_ru, re.IGNORECASE)
    if weeks_match:
        return (
            f"⏱ <b>СРОКИ ВОССТАНОВЛЕНИЯ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> пропустит из-за травмы: <b>{weeks_match.group(1)}</b>."
        )

    # Полноценная тренировка
    if "full participant at practice" in text.lower():
        return (
            f"🏒 <b>ТРЕНИРОВКА В ОБЩЕЙ ГРУППЕ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> восстановился после повреждения и тренировался без ограничений."
        )

    # Выбыл по ходу матча
    if "left" in text.lower() and "will not return" in text.lower():
        return (
            f"🚑 <b>ТРАВМА В МАТЧЕ</b>\n\n"
            f"{pos} «{team}» <b>{player}</b> получил повреждение в ходе игры и не смог вернуться на лёд."
        )
    return None

# ГЛАВНЫЙ СБОРЩИК
def build_telegram_post(player: str, pos_en: str, team: str, category: str, text: str, source: str) -> str:
    pos_ru = POSITIONS.get(pos_en, pos_en)
    
    # Последовательно проверяем категорию через профильные шаблоны
    post = None
    if category == "Signing":
        post = format_signing(player, pos_ru, team, text)
    elif category == "Trade":
        post = format_trade(player, pos_ru, team, text)
    elif category == "Waiver Move":
        post = format_waiver(player, pos_ru, team, text)
    elif category in ["Call Up", "Send Down"]:
        post = format_roster_move(player, pos_ru, team, text, category)
    elif category == "Line Change":
        post = format_line_change(player, pos_ru, team, text)
    elif category == "Injury":
        post = format_injury(player, pos_ru, team, text)

    # Если шаблон не совпал с деталями — отдаем общий аккуратный пост
    if not post:
        post = (
            f"📢 <b>{category.upper()} | «{team}»</b>\n\n"
            f"<b>{player}</b> ({pos_ru})\n"
            f"{clean_days(clean_injury(text))}"
        )

    if source:
        post += f"\n\n<i>Источник: {source}</i>"
        
    return post
