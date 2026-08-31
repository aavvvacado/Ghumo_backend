import logging
from typing import List, Dict, Any
from app.services.cloudflare_service import cloudflare_service
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class CloudflareCrawler:
    async def scrape_travel_data(self, location: str) -> str:
        """
        Scrape comprehensive travel data using Cloudflare Browser Rendering.
        """
        # Reduced queries to avoid aggressive rate limits
        queries = [
            f"{location} entry fees timings ticket price",
            f"{location} official tourism guide attraction info"
        ]
        
        combined_text = []
        
        for i, query in enumerate(queries):
            # Alternate search engines to avoid blocks
            if i % 2 == 0:
                search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            else:
                search_url = f"https://www.bing.com/search?q={query.replace(' ', '+')}"
            
            logger.info(f"Crawling search for: {query} via {search_url}")
            
            # Use Cloudflare to get search results
            html = await cloudflare_service.get_page_content(search_url)
            if not html:
                continue
            
            soup = BeautifulSoup(html, 'html.parser')
            # Improved link extraction
            links = []
            for a in soup.select('a'):
                href = a.get('href', '')
                if '/url?q=' in href: # Google
                    clean_url = href.split('/url?q=')[1].split('&')[0]
                    if 'google.com' not in clean_url and not clean_url.endswith('.pdf'):
                        links.append(clean_url)
                elif href.startswith('http') and not any(x in href for x in ['google', 'bing', 'microsoft']):
                    links.append(href)
            
            # Take top 2 links and scrape them
            for url in list(set(links))[:2]:
                await asyncio.sleep(2) # Small delay to avoid rate limits
                logger.info(f"Scraping via Cloudflare /content: {url}")
                html_res = await cloudflare_service.get_page_content(url)
                if html_res:
                    soup_page = BeautifulSoup(html_res, 'html.parser')
                    # Remove script and style elements
                    for script in soup_page(["script", "style"]):
                        script.decompose()
                    
                    title = soup_page.title.string if soup_page.title else "No Title"
                    # Get text and clean it up
                    content = soup_page.get_text(separator='\n')
                    clean_content = "\n".join([line.strip() for line in content.splitlines() if line.strip()])
                    
                    combined_text.append(f"Source: {url}\nTitle: {title}\nContent: {clean_content[:4000]}\n")
        
        return "\n".join(combined_text)

cloudflare_crawler = CloudflareCrawler()
