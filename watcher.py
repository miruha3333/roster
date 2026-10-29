import re
import hashlib
from bs4 import BeautifulSoup

# ... (предыдущий код watcher.py до извлечения текста)

    soup = BeautifulSoup(response.text, 'html.parser')
    articles = soup.find_all('article')
    
    if not articles:
        return False

    top_article = articles[0]
    raw_text = top_article.get_text(separator=" ", strip=True)

    if not raw_text or len(raw_text) < 15:
        return False

    # УБИРАЕМ ДИНАМИЧЕСКИЕ ТАЙМСТАМПЫ (например, "5m ago", "1h ago", "2 hours ago", "только что")
    # Это исключит ложные срабатывания, когда меняется только время публикации.
    clean_text = re.sub(r'\b(\d+\s*(m|h|d|min|hr|hour|ago|мин|час|д назад))\b', '', raw_text, flags=re.IGNORECASE)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    top_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()

    if not is_hash_in_db(top_hash):
        print(f"[Watcher] Обнаружена реально новая запись! (Хэш: {top_hash[:8]})")
        return True

    print([f"[Watcher] Изменений нет (таймстамп обновился, но суть та же)."])
    return False
