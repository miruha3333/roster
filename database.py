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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def generate_hash(player: str, team: str, text: str) -> str:
    """Генерирует уникальный цифровой отпечаток новости"""
    raw_key = f"{player.strip().lower()}_{team.strip().lower()}_{text.strip()[:60].lower()}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

def is_already_published(news_hash: str) -> bool:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM posted_news WHERE news_hash = ?", (news_hash,))
        return cursor.fetchone() is not None

def mark_as_published(news_hash: str, player: str, category: str):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO posted_news (news_hash, player_name, category) VALUES (?, ?, ?)",
            (news_hash, player, category)
        )
        conn.commit()
