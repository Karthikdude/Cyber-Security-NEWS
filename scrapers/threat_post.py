from typing import List
import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime
import hashlib
from core.scraper_base import BaseScraper
from core.models import Article
import logging

logger = logging.getLogger(__name__)

class ThreatPostScraper(BaseScraper):
    RSS_URL = "https://threatpost.com/feed/"

    async def fetch_articles(self) -> List[Article]:
        articles = []
        try:
            content = await self.http_client.fetch(self.RSS_URL)
            if not content:
                return []

            feed = feedparser.parse(content)
            
            for entry in feed.entries:
                try:
                    title = entry.title
                    link = entry.link
                    summary = entry.description if 'description' in entry else ""
                    
                    published_at = None
                    if 'published' in entry:
                        try:
                            published_at = parsedate_to_datetime(entry.published)
                        except Exception:
                            logger.warning(f"Could not parse date: {entry.published}")

                    content_hash = hashlib.md5(link.encode()).hexdigest()

                    article = Article(
                        title=title,
                        url=link,
                        source="Threat Post",
                        published_at=published_at,
                        summary=summary,
                        content_hash=content_hash
                    )
                    articles.append(article)
                except Exception as e:
                    logger.error(f"Error parsing entry: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping Threat Post: {e}")
            
        return articles

    async def enrich_article(self, article: Article):
        """
        Custom enrichment for Threat Post
        Targets specific content div to avoid boilerplate
        """
        try:
            logger.info(f"Enriching article: {article.title}")
            html = await self.http_client.fetch(article.url)
            if html:
                from bs4 import BeautifulSoup
                import re
                
                soup = BeautifulSoup(html, 'lxml')
                
                # ThreatPost specific selectors
                # Try specific content classes first
                article_body = (soup.find('div', class_='c-article__content') or 
                               soup.find('div', class_='post-content') or
                               soup.find('div', class_='entry-content'))
                
                if not article_body:
                    await super().enrich_article(article)
                    return
                
                # Remove boilerplate if present
                for boilerplate in article_body.find_all(string=re.compile("Infosec Insider content is written by")):
                    if boilerplate.parent:
                        boilerplate.parent.decompose()
                        
                # Extract paragraphs using base logic, but restricted to our body
                paragraphs = []
                for p in article_body.find_all(['p', 'h2', 'h3']):
                    # Handle links inline
                    for link in p.find_all('a'):
                        link_text = link.get_text()
                        link_url = link.get('href', '')
                        
                        if link_url and link_url.startswith('http') and link_text.strip():
                            if link_url not in link_text and len(link_url) < 100:
                                link.replace_with(f"{link_text} ({link_url})")
                            else:
                                link.replace_with(link_text)
                        else:
                            link.replace_with(link_text)
                    
                    para_text = p.get_text(separator=" ", strip=True)
                    para_text = re.sub(r'\s+', ' ', para_text)
                    
                    if para_text.strip() and "Infosec Insider" not in para_text:
                        paragraphs.append(para_text.strip())
                
                text_content = '\n\n'.join(paragraphs)
                
                if text_content:
                    article.content = text_content
                    if not article.summary:
                        article.summary = text_content[:500] + "..."
                else:
                    # Fallback if specific extraction failed
                    await super().enrich_article(article)
                    
        except Exception as e:
            logger.warning(f"Failed to enrich article {article.url}: {e}")
