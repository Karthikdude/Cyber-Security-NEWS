import telegram
import os
import logging
import asyncio
from typing import List, Tuple
from core.models import Article

logger = logging.getLogger(__name__)

class TelegramPublisher:
    def __init__(self):
        """
        Initialize Telegram publisher with support for:
        1. Single bot + single group (backward compatible)
        2. Single bot + multiple groups
        3. Multiple bots with their respective groups
        """
        self.bot_configs: List[Tuple[telegram.Bot, List[str]]] = []
        self._load_configurations()

    def _load_configurations(self):
        """
        Load bot configurations from environment variables.
        Supports multiple configuration formats with backward compatibility.
        """
        # Try numbered bot configuration first (TELEGRAM_BOT_TOKEN_1, etc.)
        numbered_bots = self._load_numbered_bots()
        
        if numbered_bots:
            self.bot_configs = numbered_bots
            logger.info(f"Loaded {len(numbered_bots)} bot configuration(s) with numbered format")
            for idx, (bot, chat_ids) in enumerate(numbered_bots, 1):
                logger.info(f"  Bot {idx}: {len(chat_ids)} group(s)")
            return
        
        # Fall back to simple format (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
        simple_config = self._load_simple_config()
        
        if simple_config:
            self.bot_configs = [simple_config]
            bot, chat_ids = simple_config
            logger.info(f"Loaded single bot configuration: {len(chat_ids)} group(s)")
        else:
            logger.warning("No Telegram credentials found. Publishing disabled.")

    def _load_numbered_bots(self) -> List[Tuple[telegram.Bot, List[str]]]:
        """
        Load multiple bot configurations using numbered format:
        TELEGRAM_BOT_TOKEN_1, TELEGRAM_CHAT_IDS_1
        TELEGRAM_BOT_TOKEN_2, TELEGRAM_CHAT_IDS_2, etc.
        """
        configs = []
        bot_num = 1
        
        while True:
            token_key = f"TELEGRAM_BOT_TOKEN_{bot_num}"
            chat_ids_key = f"TELEGRAM_CHAT_IDS_{bot_num}"
            
            token = os.getenv(token_key)
            chat_ids_str = os.getenv(chat_ids_key)
            
            # Stop when we don't find the next numbered bot
            if not token:
                break
            
            if not chat_ids_str:
                logger.warning(f"{token_key} found but {chat_ids_key} is missing. Skipping bot {bot_num}.")
                bot_num += 1
                continue
            
            # Parse comma-separated chat IDs
            chat_ids = [cid.strip() for cid in chat_ids_str.split(',') if cid.strip()]
            
            if chat_ids:
                bot = telegram.Bot(token=token)
                configs.append((bot, chat_ids))
                logger.debug(f"Bot {bot_num}: {len(chat_ids)} group(s)")
            
            bot_num += 1
        
        return configs

    def _load_simple_config(self) -> Tuple[telegram.Bot, List[str]] | None:
        """
        Load simple single-bot configuration (backward compatible):
        TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
        
        TELEGRAM_CHAT_ID can be:
        - Single ID: -1001234567890
        - Multiple IDs (comma-separated): -1001234567890,-1009876543210
        """
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        chat_id_str = os.getenv("TELEGRAM_CHAT_ID")
        
        if not token or not chat_id_str:
            return None
        
        # Parse chat IDs (supports both single and comma-separated)
        chat_ids = [cid.strip() for cid in chat_id_str.split(',') if cid.strip()]
        
        if not chat_ids:
            return None
        
        bot = telegram.Bot(token=token)
        return (bot, chat_ids)

    def _convert_links_to_html(self, text: str) -> str:
        """Convert 'word (url)' format to HTML anchor tags for Telegram"""
        import re
        
        # Pattern to match: up to 5 words before (http://url)
        # Only captures the actual linked text, not entire paragraphs
        # \b ensures word boundaries
        pattern = r'(\b[\w\s-]{1,50}?)\s*\((https?://[^\)]+)\)'
        
        def replace_link(match):
            link_text = match.group(1).strip()
            url = match.group(2).strip()
            return f'<a href="{url}">{link_text}</a>'
        
        # Replace all matches
        converted = re.sub(pattern, replace_link, text)
        return converted
    
    async def publish(self, articles: List[Article]):
        """
        Publish articles to all configured Telegram groups across all bots.
        Each article is sent to every group of every bot.
        """
        if not self.bot_configs:
            logger.warning("No Telegram bots configured. Skipping publish.")
            return

        for article in articles:
            # Count total successful publishes for this article
            total_published = 0
            total_groups = sum(len(chat_ids) for _, chat_ids in self.bot_configs)
            
            # Publish to all bots and their groups
            for bot_idx, (bot, chat_ids) in enumerate(self.bot_configs, 1):
                for chat_id in chat_ids:
                    try:
                        # Prepare message (same logic as before)
                        message = self._prepare_message(article)
                        
                        # Add retry logic for 429 errors
                        max_retries = 3
                        for attempt in range(max_retries):
                            try:
                                await bot.send_message(
                                    chat_id=chat_id,
                                    text=message,
                                    parse_mode=telegram.constants.ParseMode.HTML,
                                    disable_web_page_preview=True
                                )
                                total_published += 1
                                logger.info(f"Published '{article.title}' to bot {bot_idx}, group {chat_id}")
                                
                                # Respect Telegram rate limits: 1 message per second per chat limit
                                # Global limit is 30 messages per second
                                # Safe delay: 3 seconds between messages
                                await asyncio.sleep(3)
                                break
                            except Exception as e:
                                error_str = str(e).lower()
                                if "429" in error_str or "flood" in error_str or "retry" in error_str:
                                    wait_time = 30  # Default long wait
                                    # Try to parse wait time from error message if possible
                                    # e.g. "Flood control exceeded. Retry in 26 seconds"
                                    import re
                                    match = re.search(r'retry in (\d+) seconds', error_str)
                                    if match:
                                        wait_time = int(match.group(1)) + 5
                                    
                                    if attempt < max_retries - 1:
                                        logger.warning(f"⚠️ Rate limit hit. Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                                        await asyncio.sleep(wait_time)
                                        continue
                                
                                # If not rate limit error, or retries exhausted, re-raise to outer except
                                raise e
                                
                    except Exception as e:
                        logger.error(f"Error publishing to bot {bot_idx}, group {chat_id}: {e}")
            
            # Summary log for this article
            if total_published > 0:
                logger.info(f"✓ Article '{article.title}' published to {total_published}/{total_groups} group(s)")
            else:
                logger.error(f"✗ Article '{article.title}' failed to publish to any group")

    def _prepare_message(self, article: Article) -> str:
        """Prepare formatted message for Telegram"""
        # Telegram message limit is 4096 characters
        MAX_LENGTH = 3800  # Leave room for title, source, score
        
        # Prepare full content
        full_content = article.content if article.content else article.summary
        
        # Clean content: remove common problematic characters
        clean_content = full_content
        clean_content = clean_content.replace('\u200b', '')  # Zero-width space
        clean_content = clean_content.replace('\ufeff', '')  # BOM
        
        # Truncate if needed
        if len(clean_content) > MAX_LENGTH:
            content_to_send = clean_content[:MAX_LENGTH] + "..."
        else:
            content_to_send = clean_content
        
        # Convert plain text links to HTML anchor tags
        content_with_links = self._convert_links_to_html(content_to_send)
        
        # Clean, simple message format
        message = (
            f"<b>{article.title}</b>\n\n"
            f"{content_with_links}\n\n"
            f"<i>Source: {article.source}</i>\n"
            f"<i>Score: {article.score}/10</i>\n\n"
            f"<a href='{article.url}'>Article Link</a>"
        )
        
        # Final safety check for message length
        if len(message) > 4096:
            # Recalculate
            overhead = len(article.title) + len(article.source) + len(article.url) + 150
            available = 4096 - overhead
            content_to_send = clean_content[:available] + "..."
            content_with_links = self._convert_links_to_html(content_to_send)
            
            message = (
                f"<b>{article.title}</b>\n\n"
                f"{content_with_links}\n\n"
                f"<i>Source: {article.source}</i>\n"
                f"<i>Score: {article.score}/10</i>\n\n"
                f"<a href='{article.url}'>Article Link</a>"
            )
        
        return message



