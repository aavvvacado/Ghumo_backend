from app.crawlers.base import BaseCrawler
from bs4 import BeautifulSoup
import httpx
import logging
import asyncio
import random

logger = logging.getLogger(__name__)

class IndianSourcesCrawler(BaseCrawler):
    def __init__(self):
        self.trusted_domains = [
            "tripoto.com",
            "inditales.com",
            "devilonwheels.com",
            "traveltriangle.com",
            "outlookindia.com/traveller"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        }

    async def find_indian_gems(self, query: str):
        """
        Search for hidden gems specifically on trusted Indian travel platforms with a broad fallback.
        """
        search_query = f"site:{' OR site:'.join(self.trusted_domains[:3])} {query} hidden gems offbeat"
        google_url = f"https://www.google.com/search?q={search_query}"
        
        blog_urls = []
        try:
            content = await self.get_page_content(google_url)
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract URLs - try modern layout first
            for result in soup.select('div.g'):
                link = result.select_one('a[href]')
                if link:
                    url = link['href']
                    if any(domain in url for domain in self.trusted_domains):
                        blog_urls.append(url)
                if len(blog_urls) >= 5: break
            
            # Fallback parsing
            if not blog_urls:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if "url?q=" in href:
                        url = href.split("url?q=")[1].split("&")[0]
                        if any(domain in url for domain in self.trusted_domains):
                            blog_urls.append(url)
                    if len(blog_urls) >= 5: break
        except Exception as e:
            logger.error(f"Failed to find Indian specific gems for {query}: {e}")

        # Broad Search Fallback if trusted sites fail
        if not blog_urls:
            logger.info(f"No trusted results for {query}. Trying broad Indian travel search...")
            broad_query = f"{query} hidden gems offbeat travel blogs india"
            broad_url = f"https://www.google.com/search?q={broad_query}"
            try:
                content = await self.get_page_content(broad_url)
                soup = BeautifulSoup(content, 'html.parser')
                for a in soup.find_all('a', href=True):
                    if "url?q=" in a['href']:
                        url = a['href'].split("url?q=")[1].split("&")[0]
                        if url.startswith('http') and not any(x in url for x in ["google.com", "youtube.com"]):
                            blog_urls.append(url)
                    if len(blog_urls) >= 3: break
            except: pass

        scraped_data = []
        async with httpx.AsyncClient(headers=self.headers, follow_redirects=True, timeout=15.0) as client:
            for url in blog_urls:
                try:
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                    logger.info(f"Scraping source: {url}")
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        page_soup = BeautifulSoup(resp.text, 'html.parser')
                        for s in page_soup(["script", "style", "nav", "footer", "header"]):
                            s.decompose()
                        text = page_soup.get_text(separator=' ', strip=True)
                        scraped_data.append({
                            "url": url,
                            "content": text[:3000],
                            "source": url.split('/')[2]
                        })
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")

        return scraped_data

indian_sources_crawler = IndianSourcesCrawler()
