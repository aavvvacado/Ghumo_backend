import httpx
import asyncio
import time
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class RedditService:
    def __init__(self):
        self.base_url = "https://www.reddit.com/search.json"
        self.headers = {
            "User-Agent": "GhumoTravelBot/1.0"
        }
        self.last_request_time = 0
        self.request_delay = 2.0 # 2 seconds rate limit as requested

    async def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    async def search_discussions(self, query: str) -> str:
        """
        Fetch Reddit discussions for a query and return combined text.
        """
        await self._rate_limit()
        
        params = {
            "q": query,
            "sort": "relevance",
            "t": "year"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(self.base_url, params=params, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                posts = data.get("data", {}).get("children", [])
                combined_text = []
                
                for post in posts[:30]: # Limit to top 30 posts
                    pdata = post.get("data", {})
                    title = pdata.get("title", "")
                    body = pdata.get("selftext", "")
                    subreddit = pdata.get("subreddit", "")
                    score = pdata.get("score", 0)
                    
                    combined_text.append(f"Subreddit: r/{subreddit} | Score: {score}")
                    combined_text.append(f"Title: {title}")
                    if body:
                        combined_text.append(f"Content: {body[:1000]}...") # Truncate body
                    combined_text.append("-" * 30)
                
                return "\n".join(combined_text)
        except Exception as e:
            logger.error(f"Reddit search failed for {query}: {e}")
            return ""

reddit_service = RedditService()
