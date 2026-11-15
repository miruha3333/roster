import sqlite3
import hashlib

DB_FILE = "news.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posted_news (
                news_hash TEXT PRIMARY KEY,
                player_name TEXT,
                category TEXT,
                post_text TEXT,
                post_hash TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("PRAGMA table_info(posted_news)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        if "post_text" not in existing_columns:
            cursor.execute("ALTER TABLE posted_news ADD COLUMN post_text TEXT")
        if "post_hash" not in existing_columns:
            cursor.execute("ALTER TABLE posted_news ADD COLUMN post_hash TEXT")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posted_news_post_hash ON posted_news (post_hash)")
        conn.commit()

def generate_hash(player: str, team: str, text: str) -> str:
    """Генерирует уникальный цифровой отпечаток новости"""
    raw_key = f"{player.strip().lower()}_{team.strip().lower()}_{text.strip()[:60].lower()}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def generate_post_hash(post_text: str) -> str:
    """Генерирует цифровой отпечаток готового поста для Telegram"""
    normalized = "\n".join(line.strip() for line in post_text.strip().lower().splitlines())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def is_already_published(news_hash: str) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM posted_news WHERE news_hash = ?", (news_hash,))
        return cursor.fetchone() is not None

def is_post_already_published(post_text: str) -> bool:
    """Проверяет, был ли уже опубликован такой готовый пост в Telegram"""
    if not post_text:
        return False
    post_hash = generate_post_hash(post_text)
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM posted_news WHERE post_hash = ? OR post_text = ?",
            (post_hash, post_text)
        )
        return cursor.fetchone() is not None

def mark_as_published(news_hash: str, player: str, category: str, post_text: str = ""):
    post_hash = generate_post_hash(post_text) if post_text else None
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO posted_news (news_hash, player_name, category, post_text, post_hash) VALUES (?, ?, ?, ?, ?)",
            (news_hash, player, category, post_text, post_hash)
        )
        conn.commit()
