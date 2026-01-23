import sqlite_utils
from core.models import Article
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str = "news.db", enabled: bool = True):
        """
        Initialize database with optional disable mode.
        
        Args:
            db_path: Path to SQLite database file
            enabled: If False, all operations are no-ops (in-memory tracking only)
        """
        self.enabled = enabled
        self.db_path = db_path
        
        if self.enabled:
            self.db = sqlite_utils.Database(db_path)
            self.init_db()
            self._memory_hashes = None
            logger.info(f"Database enabled: {db_path}")
        else:
            self.db = None
            # In-memory set for duplicate detection during single run
            self._memory_hashes = set()
            logger.info("Database disabled - using in-memory deduplication for this run only")

    def init_db(self):
        """Initialize database schema (only when enabled)"""
        if not self.enabled:
            return
            
        self.db["articles"].create({
            "content_hash": str,
            "title": str,
            "url": str,
            "source": str,
            "published_at": str, # Stored as ISO string
            "score": float,
            "posted": int # 0 or 1
        }, pk="content_hash", if_not_exists=True)

    def article_exists(self, content_hash: str) -> bool:
        """
        Check if article exists.
        When disabled: checks in-memory set (only for current run)
        When enabled: checks database (persistent)
        """
        if not self.enabled:
            return content_hash in self._memory_hashes
        
        try:
            self.db["articles"].get(content_hash)
            return True
        except:
            return False

    def save_article(self, article: Article):
        """
        Save article to database.
        When disabled: only adds hash to in-memory set
        When enabled: saves to SQLite database
        """
        if not self.enabled:
            self._memory_hashes.add(article.content_hash)
            return
            
        try:
            self.db["articles"].insert({
                "content_hash": article.content_hash,
                "title": article.title,
                "url": article.url,
                "source": article.source,
                "published_at": article.published_at.isoformat() if article.published_at else None,
                "score": article.score,
                "posted": 0
            }, ignore=True) # Ignore if exists (handled by article_exists check usually, but good for safety)
        except Exception as e:
            logger.error(f"Error saving article {article.title}: {e}")

    def mark_as_posted(self, content_hash: str):
        """
        Mark article as posted to Telegram.
        When disabled: no-op
        When enabled: updates database record
        """
        if not self.enabled:
            return
            
        self.db["articles"].update(content_hash, {"posted": 1})
