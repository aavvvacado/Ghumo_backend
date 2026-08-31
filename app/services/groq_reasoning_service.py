import json
import logging
from app.services.ai_service import ai_service
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class GroqReasoningService:
    async def synthesize_travel_data(self, location: str, osm_data: List[Dict], reddit_text: str, blog_text: str) -> Dict[str, Any]:
        """
        Use Groq (via AIService) to synthesize data from multiple sources.
        """
        osm_summary = "\n".join([f"- {p['name']} ({p['category']}) [Lat: {p.get('lat')}, Lng: {p.get('lng')}]" for p in osm_data[:40]])
        
        prompt = f"""
        You are 'Ghumo Buddy', an expert, opinionated, and highly proactive travel intelligence engine. 
        Your goal is to synthesize data into actionable, high-quality travel advice for {location}.

        ### OpenStreetMap Places:
        {osm_summary}

        ### Reddit Discussions (Social Sentiment):
        {reddit_text}

        ### Blog Insights (Deep Context):
        {blog_text}

        ### GUIDELINES:
        1. **Travel Buddy Persona**: Be proactive and enthusiastic. Tell the user *why* they should care (e.g., "The local favorite for authentic sweets", "Perfect for a quiet evening stroll").
        2. **Creative Discovery (Hidden Gems)**: 
           - **CRITICAL**: If the blog/reddit data is empty, YOU MUST STILL FIND 2-3 'hidden gems' from the OpenStreetMap Places list. 
           - Look for places that are NOT 'hotels', 'malls', or 'main parks'. 
           - Pick anything that sounds 'local' or 'niche' (e.g., a "Junction", a "Bazaar", a small "Mandir", a "Chowk").
           - **Example**: If you see "Bhojipura Junction" in OSM, tag it as a hidden gem and say "A bustling local transit junction that offers a glimpse into the raw energy of regional travel."
           - **Goal**: Never return an empty 'hidden_gems' list for an Indian city search. 
        3. **Balanced Tips**: 
           - Prioritize local food secrets and regional quirks. 
           - Only include safety warnings if they are absolutely critical.
        4. **Strict Categorization**:
           - **food/markets/attractions**: MUST be real, physical places from the OSM list or specific names from Reddit/Blogs.
           - **hidden_gems**: Real places (ideally from OSM or specific names from sources) that are 'offbeat'.
        5. **No Hallucinations**: Do not invent names.

        Return ONLY a JSON object:
        {{
            "food": [{{ "name": "...", "reason": "...", "vibe": "...", "lat": 0.00, "lng": 0.00 }}],
            "markets": [{{ "name": "...", "reason": "...", "vibe": "...", "lat": 0.00, "lng": 0.00 }}],
            "attractions": [{{ "name": "...", "reason": "...", "vibe": "...", "lat": 0.00, "lng": 0.00 }}],
            "hidden_gems": [{{ "name": "...", "reason": "...", "vibe": "...", "lat": 0.00, "lng": 0.00 }}],
            "tips": [{{ "text": "...", "category": "food|culture|logistics|safety" }}]
        }}
        """

        try:
            # We use the existing ai_service which already has Groq integrated
            response_text = await ai_service.generate_content(prompt, system_prompt="You are 'Ghumo Buddy', a proactive travel specialist.")
            
            # Extract JSON from response if it has markdown or extra text
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "{" in response_text:
                response_text = response_text[response_text.find("{"):response_text.rfind("}")+1]

            return json.loads(response_text)
        except Exception as e:
            logger.error(f"Groq reasoning failed for {location}: {e}")
            return {
                "food": [], "markets": [], "attractions": [], "hidden_gems": [], "tips": []
            }

groq_reasoning_service = GroqReasoningService()
