import httpx
import logging
import asyncio
import random
from typing import Dict, Any, Optional, List
from app.utils.config import settings

logger = logging.getLogger(__name__)

class CloudflareService:
    def __init__(self):
        self.account_id = settings.CLOUDFLARE_ACCOUNT_ID
        self.auth_token = settings.CLOUDFLARE_AUTH_TOKEN
        self.base_url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/browser-rendering"
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

    async def _request_with_retry(self, method: str, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """ Helper to perform requests with exponential backoff on 429 errors. """
        max_retries = 3
        base_delay = 5.0
        
        async with httpx.AsyncClient() as client:
            for i in range(max_retries):
                try:
                    if method.upper() == "POST":
                        resp = await client.post(endpoint, headers=self.headers, **kwargs)
                    else:
                        resp = await client.get(endpoint, headers=self.headers, **kwargs)
                    
                    if resp.status_code == 429:
                        wait_time = base_delay * (2 ** i) + random.uniform(0, 1)
                        logger.warning(f"Cloudflare 429: Rate limit exceeded. Retrying in {wait_time:.1f}s...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    return resp
                except Exception as e:
                    logger.error(f"Cloudflare request failed: {e}")
                    if i == max_retries - 1: return None
                    await asyncio.sleep(2.0)
            return None

    async def start_crawl(self, url: str, max_pages: int = 5, depth: int = 1) -> Optional[str]:
        """ Start a crawl job for a given URL. Returns job_id. """
        endpoint = f"{self.base_url}/crawl"
        payload = {"url": url, "max_pages": max_pages, "depth": depth, "render": True}
        
        resp = await self._request_with_retry("POST", endpoint, json=payload, timeout=40.0)
        if not resp: return None
        
        try:
            data = resp.json()
            if isinstance(data, dict) and data.get("success"):
                job_id = data.get("result", {}).get("id")
                logger.info(f"Cloudflare crawl started for {url}. Job ID: {job_id}")
                return job_id
            logger.error(f"Cloudflare crawl start failed: {data}")
        except Exception as e:
            logger.error(f"Error parsing start_crawl response: {e}")
        return None

    async def get_crawl_results(self, job_id: str) -> List[Dict[str, Any]]:
        """ Poll for crawl results until finished or timeout. """
        endpoint = f"{self.base_url}/crawl/{job_id}"
        
        for i in range(30):
            resp = await self._request_with_retry("GET", endpoint, timeout=20.0)
            if not resp: return []
            
            try:
                data = resp.json()
                if not isinstance(data, dict): return []
                
                result = data.get("result", {})
                status = result.get("status")
                logger.info(f"Crawl job {job_id} attempt {i+1} status: {status}")
                
                if status == "finished": return result.get("pages", [])
                elif status == "failed":
                    logger.error(f"Cloudflare crawl job {job_id} failed: {result}")
                    return []
            except Exception as e:
                logger.error(f"Error parsing get_crawl_results: {e}")
                return []
            
            await asyncio.sleep(2)
        return []

    async def get_page_content(self, url: str) -> Optional[str]:
        """ Quickly get the HTML content of a single page using Browser Rendering. """
        endpoint = f"{self.base_url}/content"
        payload = {"url": url}
        
        resp = await self._request_with_retry("POST", endpoint, json=payload, timeout=60.0)
        if resp:
            try:
                data = resp.json()
                if isinstance(data, dict) and data.get("success"):
                    res = data.get("result")
                    return res if isinstance(res, str) else res.get("content")
            except Exception as e:
                logger.error(f"Error parsing /content response: {e}")

        # Fallback to a depth-0 crawl
        logger.info(f"Falling back to depth-0 crawl for {url}")
        job_id = await self.start_crawl(url, max_pages=1, depth=0)
        if job_id:
            results = await self.get_crawl_results(job_id)
            if results: return results[0].get("content")
        return None

cloudflare_service = CloudflareService()
