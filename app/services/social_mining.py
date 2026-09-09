import logging
from typing import Dict, Any, List
import json
from app.services.youtube_service import youtube_service
from app.services.ai_service import ai_service
from app.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)

class SocialMining(BaseCrawler):
    async def process_video_url(self, url: str) -> Dict[str, Any]:
        """
        Takes an Instagram/FB Reel or YouTube link, extracts the text/transcript (or mocks it for secure/locked platforms),
        and prompts the AI to plan a complete itinerary and list of places from it.
        """
        text_content = ""
        
        try:
            # Check if it's youtube
            if "youtube.com" in url or "youtu.be" in url:
                # We can search by title or just extract the ID
                import urllib.parse as urlparse
                from youtube_transcript_api import YouTubeTranscriptApi
                
                parsed = urlparse.urlparse(url)
                video_id = urlparse.parse_qs(parsed.query).get('v')
                if not video_id:
                    if "youtu.be" in url:
                        video_id = [parsed.path.lstrip('/')]
                    elif "/shorts/" in parsed.path:
                        # Extract shorts video ID
                        video_id = [parsed.path.split('/shorts/')[1].split('?')[0]]
                        
                if video_id:
                    text_content = await youtube_service.fetch_video_data(video_id[0])
                else:
                    text_content = f"Could not extract video ID from {url}."
                    
            elif "instagram.com" in url or "facebook.com" in url:
                # Mock extraction for Instagram/FB reels to avoid login/captcha blocks
                logger.info(f"Using advanced fallback text extraction for social link to avoid blocks: {url}")
                title_html = await self.get_page_content(url)
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(title_html, 'html.parser')
                title = soup.title.string if soup.title else ""
                
                # If direct title is blocked/empty, try search fallback
                if not title or "facebook" in title.lower() or "error" in title.lower():
                    logger.info(f"Direct FB/IG title blocked. Trying search fallback for: {url}")
                    search_content = await self.get_page_content(f"https://html.duckduckgo.com/html/?q={url}")
                    search_soup = BeautifulSoup(search_content, 'html.parser')
                    result_link = search_soup.find('a', class_='result__a')
                    if result_link:
                        title = result_link.get_text()
                        logger.info(f"Found title via search fallback: {title}")
                
                if not title:
                    title = "Social Video (Content Restricted)"
                
                # Try to extract hints from URL path
                url_hints = " ".join(re.findall(r'[a-zA-Z]{3,}', url))
                text_content = f"Social Video Title/Metadata: {title}. URL Path Hints: {url_hints}. Provide an itinerary if you can infer the location from hints, otherwise guide the user."
                
            else:
                text_content = "Unknown video source."

        except Exception as e:
            logger.error(f"Failed to extract video content: {e}")
            text_content = f"Error extracting: {e}"

        prompt = f"""
        You are Ghumo Buddy, an expert travel planner.
        I found a travel video at: {url}
        
        Here is the extracted transcript, metadata, or comments:
        "{text_content}"
        
        Using the above info (or the URL title if you can infer it), please:
        1. Identify the Main City/Region.
        2. Generate a vibrant itinerary.
        3. List recommended food spots or landmarks.
        
        If the context is completely empty or error-prone, attempt to guess the location from the URL or title if provided, 
        otherwise state that you need a transcript or more info in a friendly way.
        
        Return ONLY valid JSON:
        {{
            "location": "Main city or region",
            "itinerary": "A vibrant paragraph describing the plan...",
            "recommended_places": [
                {{"name": "...", "type": "food", "reason": "...", "lat": 0.00, "lng": 0.00}}
            ]
        }}
        """

        try:
            response_text = await ai_service.generate_content(prompt, system_prompt="Answer in purely JSON.")
            
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "{" in response_text:
                response_text = response_text[response_text.find("{"):response_text.rfind("}")+1]

            return json.loads(response_text)
            
        except Exception as e:
            logger.error(f"Failed to generate video itinerary: {e}")
            return {
                "location": "Unknown",
                "itinerary": "Could not determine.",
                "recommended_places": []
            }

social_mining = SocialMining()
