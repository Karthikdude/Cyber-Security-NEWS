import logging
import asyncio
import os
from dotenv import load_dotenv

from core.http_client import HTTPClient
from core.db import Database
from core.ai import GeminiScorer
from core.publisher import TelegramPublisher

# Working scrapers (8 verified)
from scrapers.hacker_news import HackerNewsScraper
from scrapers.bleeping_computer import BleepingComputerScraper
from scrapers.threat_post import ThreatPostScraper
from scrapers.infosecurity_magazine import InfoSecurityMagazineScraper
from scrapers.security_affairs import SecurityAffairsScraper
from scrapers.cyber_scoop import CyberScoopScraper
from scrapers.cso_online import CSOOnlineScraper
from scrapers.cybersecurity_news import CybersecurityNewsScraper


# Load env
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

async def main():
    logger.info("Starting Cyber-NEWS Aggregator...")
    
    # Initialize components
    http = HTTPClient()
    
    # Database - supports optional disable via ENABLE_DATABASE env var
    db_enabled = os.getenv("ENABLE_DATABASE", "true").lower() in ("true", "1", "yes")
    db = Database(enabled=db_enabled)
    
    scorer = GeminiScorer()
    publisher = TelegramPublisher()
    
    # Scrapers - 8 verified working scrapers
    scrapers = [
        HackerNewsScraper(http),
        BleepingComputerScraper(http),
        ThreatPostScraper(http),
        InfoSecurityMagazineScraper(http),
        SecurityAffairsScraper(http),
        CyberScoopScraper(http),
        CSOOnlineScraper(http),
        CybersecurityNewsScraper(http),
    ]
    
    all_articles = []
    
    # 1. Scrape
    for scraper in scrapers:
        logger.info(f"Running scraper: {scraper.name}")
        try:
            articles = await scraper.fetch_articles()
            logger.info(f"Found {len(articles)} articles from {scraper.name}")
            all_articles.extend(articles)
        except Exception as e:
            logger.error(f"Scraper {scraper.name} failed: {e}")
            
    # 2. Filter & Deduplicate
    new_articles = []
    for article in all_articles:
        if not db.article_exists(article.content_hash):
            new_articles.append(article)
        else:
            logger.debug(f"Duplicate article skipped: {article.title}")
            
    logger.info(f"Found {len(new_articles)} new articles (after deduplication)")
    
    
    # 2.5 BATCH FILTERING WITH IMMEDIATE PROCESSING
    # Process each batch immediately: filter → enrich → score → publish
    if len(new_articles) > 0:
        logger.info(f"Starting streaming batch processing of {len(new_articles)} articles...")
        
        published_count = 0
        total_approved = 0
        batch_size = 40
        
        for batch_num in range(0, len(new_articles), batch_size):
            batch = new_articles[batch_num:batch_num + batch_size]
            logger.info(f"\n🔄 Processing batch {batch_num//batch_size + 1} ({len(batch)} articles)...")
            
            # Step 1: Filter this batch by titles
            approved_batch = await scorer.batch_filter_articles(batch, batch_size=len(batch))
            total_approved += len(approved_batch)
            logger.info(f"  ✅ Approved {len(approved_batch)}/{len(batch)} articles in this batch")
            
            if not approved_batch:
                continue
            
            # Step 2: Enrich approved articles in this batch
            logger.info(f"  📥 Enriching {len(approved_batch)} articles...")
            for article in approved_batch:
                if not article.content:
                    await scrapers[0].enrich_article(article)
            
            # Step 3: Score and publish immediately
            logger.info(f"  🎯 Scoring and publishing...")
            for idx, article in enumerate(approved_batch, 1):
                score = await scorer.score_article(article)
                article.score = score
                db.save_article(article)
                
                if score >= 6.0:
                    logger.info(f"    📰 [{idx}/{len(approved_batch)}] Score: {score} - Publishing!")
                    await publisher.publish([article])
                    db.mark_as_posted(article.content_hash)
                    published_count += 1
                else:
                    logger.info(f"    ⏭️  [{idx}/{len(approved_batch)}] Score: {score} - Skipped")
        
        logger.info(f"\n✅ Batch processing complete!")
        logger.info(f"   Total approved: {total_approved}/{len(new_articles)}")
        logger.info(f"   Total published: {published_count}")
    else:
        logger.info("No new articles to process.")

if __name__ == "__main__":
    asyncio.run(main())
