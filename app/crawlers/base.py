import httpx
import logging
import random
import asyncio

logger = logging.getLogger(__name__)

class BaseCrawler:
    async def get_page_content(self, url: str):
        from app.utils.config import settings
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        
        proxy_url = None
        is_social = any(domain in url for domain in ["facebook.com", "instagram.com", "google.com"])
        
        if is_social and settings.WEBSHARE_USERNAME and settings.WEBSHARE_PASSWORD:
            proxy_url = f"http://{settings.WEBSHARE_USERNAME}:{settings.WEBSHARE_PASSWORD}@31.59.20.176:6754"
            logger.info(f"Using proxy for social domain: {url}")

        try:
            async with httpx.AsyncClient(proxies=proxy_url, verify=False, follow_redirects=True) as client:
                await asyncio.sleep(random.uniform(0.5, 1.5))
                res = await client.get(url, headers=headers, timeout=20.0)
                content = res.text
                
                # Check for bot detection or empty results in Google
                if "google.com" in url and ("detected unusual traffic" in content.lower() or "did not match any documents" in content.lower()):
                    logger.warning(f"Google blocked or empty for {url}. Falling back to DuckDuckGo...")
                    query = url.split("q=")[1].split("&")[0]
                    ddg_url = f"https://html.duckduckgo.com/html/?q={query}"
                    res = await client.get(ddg_url, headers=headers, timeout=15.0)
                    content = res.text

                return content
        except Exception as e:
            logger.error(f"Error fetching page {url}: {e}")
            return ""
