import google.generativeai as genai
import os
import logging
import json
from typing import Optional, List, Dict
from core.models import Article

logger = logging.getLogger(__name__)

class GeminiScorer:
    def __init__(self):
        # Load all available API keys
        self.api_keys = []
        for i in range(1, 10):  # Check for up to 10 keys
            key_name = "GEMINI_API_KEY" if i == 1 else f"GEMINI_API_KEY_{i}"
            api_key = os.getenv(key_name)
            if api_key:
                self.api_keys.append(api_key)
                logger.info(f"Loaded {key_name}")
        
        if not self.api_keys:
            logger.warning("No GEMINI_API_KEY found. AI scoring will be disabled.")
            self.model = None
            self.current_key_index = -1
        else:
            logger.info(f"Loaded {len(self.api_keys)} API key(s)")
            self.current_key_index = 0
            genai.configure(api_key=self.api_keys[self.current_key_index])
            
            # Free tier models - TESTED & VERIFIED WORKING (Jan 2026)
            self.fallback_models = [
                # Gemini models (free tier, all tested working)
                "gemini-2.5-flash",           # ✅ Working - limited (10 RPM, 20 RPD)
                "gemini-2.5-flash-lite",      # ✅ Working - best free (15 RPM, 1000 RPD)
                "gemini-2.5-pro",             # ✅ Working - limited (5 RPM, 100 RPD)
                "gemini-3-flash-preview",     # ✅ Working - latest (15 RPM, 1000 RPD)
                "gemini-2.0-flash",           # ✅ Working - good balance (15 RPM, 200 RPD)
                "gemini-2.0-flash-lite",      # ✅ Working - high throughput (30 RPM, 1000 RPD)
                
                # Gemma 3 models (100% free, generous limits - 30 RPM, 14400 RPD)
                "gemma-3-27b-it",             # ✅ Working - most capable
                "gemma-3-12b-it",             # ✅ Working - very capable (note: may be slow)
                "gemma-3-4b-it",              # ✅ Working - best speed/quality balance
                "gemma-3n-e4b-it",            # ✅ Working - edge optimized, multimodal
                "gemma-3n-e2b-it",            # ✅ Working - 2x faster, mobile friendly
                "gemma-3-1b-it",              # ✅ Working - ultra-fast, lightweight
            ]
            self.current_model_name = self.fallback_models[0]
            self.model = genai.GenerativeModel(self.current_model_name)
            logger.info(f"Using API key #{self.current_key_index + 1}, Model: {self.current_model_name}")
    
    def _rotate_api_key(self):
        """Rotate to next API key when rate limited"""
        if len(self.api_keys) <= 1:
            logger.warning("Only 1 API key available, cannot rotate")
            return False
        
        old_index = self.current_key_index
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        
        # Reconfigure with new key
        genai.configure(api_key=self.api_keys[self.current_key_index])
        self.model = genai.GenerativeModel(self.current_model_name)
        logger.info(f"🔄 ROTATED from API key #{old_index + 1} to API key #{self.current_key_index + 1}")
        return True

    async def batch_filter_articles(self, articles: List[Article], batch_size: int = 40) -> List[Article]:
        """
        Pre-filter articles by sending titles in batches to Gemini.
        Only approved articles are returned for full processing.
        """
        if not self.model:
            return articles
        
        approved_articles = []
        
        # Process in batches
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i + batch_size]
            
            # Create title list with IDs
            title_list = ""
            for idx, article in enumerate(batch):
                title_list += f"{idx + 1}. [{article.source}] {article.title}\n"
            
            prompt = f"""You are a Cyber Security News Filter. Review these {len(batch)} article titles and identify which ones are relevant and important for cybersecurity professionals.

**Criteria for approval:**
- Security vulnerabilities, exploits, CVEs
- Data breaches, attacks, incidents
- New malware, ransomware, threats
- Security patches, updates, advisories
- Significant security research or reports

**Reject:**
- Marketing fluff, product announcements without substance
- Generic tips, basic advice
- Event announcements, conferences (unless major)
- Opinion pieces without technical value

**Article Titles:**
{title_list}

**Instructions:**
Reply with ONLY a JSON object with one key "approved" containing an array of numbers (1-{len(batch)}) for articles to keep.
Example: {{"approved": [1, 3, 7, 12]}}
"""
            
            # Try all models first, THEN rotate keys
            max_attempts = len(self.api_keys) * len(self.fallback_models)
            for attempt in range(max_attempts):
                model_index = attempt % len(self.fallback_models)
                key_index = attempt // len(self.fallback_models)
                model_name = self.fallback_models[model_index]
                
                try:
                    # Switch model if needed
                    if model_name != self.current_model_name:
                        self.model = genai.GenerativeModel(model_name)
                        self.current_model_name = model_name
                        logger.info(f"📝 Trying model: {model_name}")
                    
                    response = await self.model.generate_content_async(prompt)
                    
                    # Check if response has text (might be blocked or empty)
                    if not response or not hasattr(response, 'text'):
                        logger.warning(f"Model {model_name} returned empty response, trying next...")
                        continue
                    
                    try:
                        response_text = response.text
                    except Exception as text_error:
                        logger.warning(f"Model {model_name} response has no valid text: {text_error}, trying next...")
                        continue
                    
                    data = json.loads(response_text.strip().replace('```json', '').replace('```', ''))
                    approved_ids = data.get("approved", [])
                    
                    # Add approved articles
                    for article_id in approved_ids:
                        if 1 <= article_id <= len(batch):
                            approved_articles.append(batch[article_id - 1])
                    
                    logger.info(f"Batch {i//batch_size + 1}: Approved {len(approved_ids)}/{len(batch)} articles")
                    break  # Success, move to next batch
                    
                except Exception as e:
                    error_msg = str(e).lower()
                    
                    # Handle different error types
                    if '404' in error_msg or 'not found' in error_msg:
                        # Model doesn't exist - skip to next model immediately
                        logger.warning(f"Model {model_name} not found (404), skipping to next model...")
                        continue
                    elif '429' in error_msg or 'quota' in error_msg:
                        # Quota exhausted - try next model, rotate key if all models tried
                        if model_index == len(self.fallback_models) - 1:
                            if key_index < len(self.api_keys) - 1:
                                logger.warning(f"✋ All {len(self.fallback_models)} models exhausted on key #{self.current_key_index + 1}, rotating to next key...")
                                if self._rotate_api_key():
                                    # Reset to first model with new key
                                    self.current_model_name = self.fallback_models[0]
                                    self.model = genai.GenerativeModel(self.current_model_name)
                                    logger.info(f"📝 Reset to first model: {self.current_model_name}")
                                    continue
                            else:
                                logger.error("All API keys and models exhausted. Keeping all articles in batch.")
                                approved_articles.extend(batch)
                                break
                        # Try next model
                        continue
                    else:
                        logger.warning(f"Batch filtering failed: {str(e)[:100]}. Keeping all articles.")
                        approved_articles.extend(batch)
                        break
        
        logger.info(f"Total: {len(approved_articles)}/{len(articles)} articles approved after batch filtering")
        return approved_articles

    async def score_article(self, article: Article) -> float:
        """Score individual article (called after batch filtering)"""
        if not self.model:
            return 0.0

        # Shorter prompt for small models (gemma has only 15K TPM)
        prompt = f"""Rate this cybersecurity article 0.0-10.0:

Guidelines:
9-10: Critical 0-day, major breach, industry shift
7-8: Important patch, new attack vector, notable report
5-6: Routine update, vendor news
<5: Marketing, low quality

Output JSON: {{"score": float, "reason": "short string"}}

Title: {article.title}
Content: {article.content[:800] if article.content else article.summary[:500]}
Source: {article.source}
"""

        # Try all models FIRST, then rotate keys
        max_attempts = len(self.api_keys) * len(self.fallback_models)
        for attempt in range(max_attempts):
            model_index = attempt % len(self.fallback_models)
            key_index = attempt // len(self.fallback_models)
            model_name = self.fallback_models[model_index]
            
            try:
                # Switch model if needed
                if model_name != self.current_model_name:
                    self.model = genai.GenerativeModel(model_name)
                    self.current_model_name = model_name
                    logger.info(f"📝 Trying model: {model_name}")
                
                response = await self.model.generate_content_async(prompt)
                
                # Check if response has text
                if not response or not hasattr(response, 'text'):
                    logger.warning(f"Model {model_name} returned empty response, trying next...")
                    continue
                
                try:
                    response_text = response.text
                except Exception as text_error:
                    logger.warning(f"Model {model_name} response has no valid text: {text_error}, trying next...")
                    continue
                
                data = json.loads(response_text.strip().replace('```json', '').replace('```', ''))
                score = float(data.get("score", 0.0))
                article.relevance_reason = data.get("reason", "No reason provided")
                logger.info(f"Scored '{article.title[:50]}...' = {score}")
                return score
                
            except Exception as e:
                error_msg = str(e).lower()
                
                # Handle different error types
                if '404' in error_msg or 'not found' in error_msg:
                    # Model doesn't exist - skip to next model immediately
                    logger.warning(f"Model {model_name} not found (404), skipping to next model...")
                    continue
                elif '429' in error_msg or 'quota' in error_msg:
                    # Quota exhausted - try next model, rotate key if all models tried
                    if model_index == len(self.fallback_models) - 1:  # Last model
                        if key_index < len(self.api_keys) - 1:  # More keys available
                            logger.warning(f"✋ All {len(self.fallback_models)} models exhausted on key #{self.current_key_index + 1}, rotating to next key...")
                            if self._rotate_api_key():
                                # Reset to first model with new key
                                self.current_model_name = self.fallback_models[0]
                                self.model = genai.GenerativeModel(self.current_model_name)
                                logger.info(f"📝 Reset to first model: {self.current_model_name}")
                                continue
                        else:
                            logger.warning(f"All API keys and models exhausted. Defaulting score to 5.0")
                            return 5.0
                    # Try next model
                    continue
                else:
                    logger.warning(f"Scoring failed: {str(e)[:100]}")
                    continue
        
        logger.error(f"All attempts failed for article {article.title[:50]}")
        return 5.0  # Default middle score if all fails

