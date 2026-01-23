from abc import ABC, abstractmethod
from typing import List, Optional
import logging
from readability import Document
from core.http_client import HTTPClient
from core.models import Article

logger = logging.getLogger(__name__)

class BaseScraper(ABC):
    def __init__(self, http_client: HTTPClient):
        self.http_client = http_client
        self.name = self.__class__.__name__

    @abstractmethod
    async def fetch_articles(self) -> List[Article]:
        """
        Main entry point for the scraper.
        Returns a list of Article objects.
        """
        pass

    async def enrich_article(self, article: Article):
        """
        Fetches the full content of the article using its URL.
        Updates the article.content field.
        Uses improved extraction that preserves paragraph structure.
        """
        try:
            logger.info(f"Enriching article: {article.title}")
            html = await self.http_client.fetch(article.url)
            if html:
                doc = Document(html)
                clean_html = doc.summary() # This is the main content HTML
                
                from bs4 import BeautifulSoup
                import re
                
                soup = BeautifulSoup(clean_html, 'lxml')
                
                # Try to find main content area (works for most sites)
                article_body = (soup.find('article') or 
                               soup.find('div', class_=lambda x: x and 'article' in x.lower()) or
                               soup)
                
                # Extract paragraphs properly
                paragraphs = []
                for p in article_body.find_all(['p', 'h2', 'h3']):
                    # Handle links inline - replace with text (url) format
                    for link in p.find_all('a'):
                        link_text = link.get_text()
                        link_url = link.get('href', '')
                        
                        # Replace link with text + URL for external links
                        if link_url and link_url.startswith('http') and link_text.strip():
                            if link_url not in link_text and len(link_url) < 100:
                                link.replace_with(f"{link_text} ({link_url})")
                            else:
                                link.replace_with(link_text)
                        else:
                            link.replace_with(link_text)
                    
                    # Get cleaned paragraph text
                    para_text = p.get_text(separator=" ", strip=True)
                    # Clean up extra spaces
                    para_text = re.sub(r'\s+', ' ', para_text)
                    
                    if para_text.strip():
                        paragraphs.append(para_text.strip())
                
                # Join with double newlines for paragraph breaks
                text_content = '\n\n'.join(paragraphs)
                
                article.content = text_content
                # If summary was empty, use start of content
                if not article.summary:
                    article.summary = text_content[:500] + "..."
                    
        except Exception as e:
            logger.warning(f"Failed to enrich article {article.url}: {e}")

    def normalize_date(self, date_str: str):
        # TODO: Implement date parsing
        return None
