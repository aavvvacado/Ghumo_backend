from app.crawlers.base import BaseCrawler
from bs4 import BeautifulSoup
import httpx
import logging
import re

logger = logging.getLogger(__name__)

class BlogCrawler(BaseCrawler):
    async def scrape_blogs(self, query: str):
        """
        Search for blogs related to the query and scrape their content.
        """
        # 1. Search for blog URLs (simplified search via search engine results)
        search_url = f"https://www.google.com/search?q={query}+travel+blog+tips"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        blog_urls = []
        try:
            # We use playwright from base to get search results
            content = await self.get_page_content(search_url)
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract URLs from common search engine structures
            # 1. Look for 'h3' parents which usually wrap titles in modern Google
            for result in soup.select('div.g'):
                link = result.select_one('a[href]')
                if link:
                    url = link['href']
                    if url.startswith('http') and not any(x in url for x in ["google.com", "youtube.com", "facebook.com", "twitter.com"]):
                        blog_urls.append(url)
                if len(blog_urls) >= 3:
                    break
            
            # Fallback to old format or other structures
            if not blog_urls:
                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if "url?q=" in href:
                        url = href.split("url?q=")[1].split("&")[0]
                        if url.startswith('http') and not any(x in url for x in ["google.com", "youtube.com"]):
                            blog_urls.append(url)
                    if len(blog_urls) >= 3:
                        break
        except Exception as e:
            logger.error(f"Failed to find blog URLs for {query}: {e}")

        all_text = []
        # 2. Scrape each blog page using httpx as requested
        async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=10.0) as client:
            for url in blog_urls:
                try:
                    logger.info(f"Scraping blog: {url}")
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        page_soup = BeautifulSoup(resp.text, 'html.parser')
                        # Remove script, style, and nav elements
                        for s in page_soup(["script", "style", "nav", "footer", "header"]):
                            s.decompose()
                        
                        text = page_soup.get_text(separator=' ', strip=True)
                        all_text.append(f"Source: {url}\nContent: {text[:2000]}...") # Limit text per blog
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")

        return "\n\n".join(all_text)

blog_crawler = BlogCrawler()
