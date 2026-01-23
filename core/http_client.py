import logging
import httpx
from typing import Optional
from fake_useragent import UserAgent
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class HTTPClient:
    def __init__(self):
        self.ua = UserAgent()
        self.client = httpx.AsyncClient(http2=False, follow_redirects=True)

    def _get_headers(self):
        return {
            "User-Agent": self.ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.google.com/",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def fetch(self, url: str) -> Optional[str]:
        """
        Fetches the content of a URL with retries and header rotation.
        Returns the HTML content as string, or None if failed.
        """
        try:
            headers = self._get_headers()
            response = await self.client.get(url, headers=headers, timeout=15.0)
            
            # If 403, try Google Cache
            if response.status_code == 403:
                logger.warning(f"Got 403 for {url}. Trying Google Cache...")
                cache_url = f"http://webcache.googleusercontent.com/search?q=cache:{url}"
                response = await self.client.get(cache_url, headers=headers, timeout=15.0)
            
            response.raise_for_status()
            logger.info(f"Successfully fetched {url}")
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            raise # Let tenacity handle the retry

    async def close(self):
        await self.client.aclose()
