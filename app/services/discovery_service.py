import logging
import asyncio
from app.crawlers.indian_sources import indian_sources_crawler
from app.crawlers.blog_crawler import blog_crawler
from app.database.session import SessionLocal
from app.database.models import RawScrape
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger(__name__)

class DiscoveryService:
    async def discover_local_insights(self, query: str):
        """
        Orchestrate multi-source discovery for hidden gems.
        """
        logger.info(f"Starting deep discovery for: {query}")
        
        # 1. Check local DB cache first to avoid re-scraping
        db = SessionLocal()
        try:
            existing = db.query(RawScrape).filter(RawScrape.query == query.lower()).all()
            if existing:
                logger.info(f"Found {len(existing)} cached scrapes for {query}")
                return "\n\n".join([e.content for e in existing])
        finally:
            db.close()

        # 2. Run crawlers
        indian_task = asyncio.create_task(indian_sources_crawler.find_indian_gems(query))
        generic_task = asyncio.create_task(blog_crawler.scrape_blogs(query))
        
        indian_results, generic_text = await asyncio.gather(indian_task, generic_task)
        
        # 3. Persist and prepare results
        db = SessionLocal()
        combined_text = [generic_text] if generic_text else []
        
        try:
            if not indian_results and not generic_text:
                logger.warning(f"No deep discovery found for {query}. Not caching empty result.")
                return ""

            for item in indian_results:
                content_text = f"Source: {item['url']}\nContent: {item['content']}"
                combined_text.append(content_text)
                
                # Store in RawScrape table
                try:
                    new_scrape = RawScrape(
                        url=item['url'],
                        content=item['content'],
                        source=item['source'],
                        query=query.lower()
                    )
                    db.add(new_scrape)
                    db.commit()
                except IntegrityError:
                    db.rollback() 
                except Exception as e:
                    logger.error(f"Error persisting scrape: {e}")
                    db.rollback()
        finally:
            db.close()
            
        return "\n\n".join(combined_text)

discovery_service = DiscoveryService()
