from typing import List
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
from core.scraper_base import BaseScraper
from core.models import Article
import logging
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class HackerNewsScraper(BaseScraper):
    RSS_URL = "https://feeds.feedburner.com/TheHackersNews"

    async def fetch_articles(self) -> List[Article]:
        articles = []
        try:
            # RSS is XML, we can fetch it directly
            content = await self.http_client.fetch(self.RSS_URL)
            if not content:
                return []

            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                try:
                    title = entry.title
                    link = entry.link
                    summary = entry.description if 'description' in entry else ""
                    
                    # Parse date
                    published_at = None
                    if 'published' in entry:
                        try:
                            published_at = parsedate_to_datetime(entry.published)
                        except Exception:
                            logger.warning(f"Could not parse date: {entry.published}")

                    # Generate ID
                    content_hash = hashlib.md5(link.encode()).hexdigest()

                    article = Article(
                        title=title,
                        url=link,
                        source="The Hacker News",
                        published_at=published_at,
                        summary=summary,
                        content_hash=content_hash
                    )
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping The Hacker News: {e}")
            
        return articles


