import json
import logging
from typing import Dict, Any, List
from app.services.ai_service import ai_service
from app.services.cache_service import cache_service
from app.utils.config import settings

logger = logging.getLogger(__name__)

class ContextReasoningService:
    async def synthesize_travel_data(self, location: str, osm_data: List[Dict], reddit_text: str, blog_text: str, youtube_text: str = "", deep_scraped_text: str = "") -> Dict[str, Any]:
        """
        Synthesize context using Groq API for reasoning and summarization.
        """
        import re
        # 1. Check Valkey cache for the reasoned context
        cache_key = f"reasoning:{location.lower()}"
        cached_result = await cache_service.get_cache(cache_key)
        if cached_result:
            logger.info(f"Context reasoning cache hit for {location}")
            return cached_result

        # 2. Prepare summary payload
        osm_summary = "\n".join([f"- {p['name']} ({p.get('category', 'unknown')})" for p in osm_data[:100]])
        
        prompt = f"""
        You are an expert Indian tourism assistant. Your responsibilities include:
        1. Top Tourist Destinations & Hidden Gems: Recommend best destinations and secret spots within {location}. For each, provide:
           - History: Historical significance.
           - Cultural Significance: Importance and unique features.
           - Must-See Attractions: Key spots not to miss.
           - Practical Info: Ticket prices (INR), timings, and best way to reach.
        2. Restaurant Recommendations: Suggest spots near destinations, including:
           - Dietary Preferences: Vegetarian, Non-Vegetarian, or Both.
           - Must-Try Cuisine: Renowned or unique dishes.
        3. Local Traditions & Etiquette: Describe unique traditions and what to follow or avoid.
        4. Best Time to Visit: Optimal time considering:
           - Weather, Local Festivals, and Tourist Footfall.
        5. Complete Travel Schedules: For {location}, provide a comprehensive itinerary including:
           - Significant Attractions, Cultural Experiences, and Local Specialties.
        6. Safety Alerts & Cautions: Add safety alerts (especially for kids 0-14 or seniors 50+) and what to strictly avoid.
        7. Packing Recommendations: Necessary items (Cold/Beach/General).

        - **Critical Regional Check**: Verify that the places you recommend are actually within or very near {location}. 
        - **Coordinate Matching**: The provided OSM data and coordinates point to a specific region. DO NOT recommend places in Punjab if the location is in Madhya Pradesh or Bihar. 
        - **Name Clarity**: "Sonpur" could be in Bihar or MP. Check the provided context carefully. If context is 'FALLBACK', prioritize the most famous city of that name (e.g. Sonpur, Bihar for the cattle fair).
        - **Guaranteed Results**: Even if the provided context is sparse or missing, you MUST provide at least 3 top tourist attractions and 2 renowned food spots based on your extensive knowledge of Indian tourism. NEVER return empty lists for a known location.
        - **Answer based on the provided context**: If the context is missing, thin, or contains 'FALLBACK', search your internal high-fidelity knowledge of India.
        
        ### OSM Place List
        {osm_summary}

        ### Social & Video Context
        {reddit_text}
        {youtube_text}
        {blog_text}

        ### Deep Scraped Content (Websites/Blogs)
        {deep_scraped_text}

        Return structured JSON ONLY. Ensure the JSON is complete and not truncated.
        JSON Schema:
        {{
            "places": [{{ 
                "name": "...", 
                "reason": "...", 
                "history": "...", 
                "culture": "...", 
                "must_see": "...",
                "ticket_price": "...",
                "timings": "...",
                "lat": 0.00, 
                "lng": 0.00 
            }}],
            "food": [{{ 
                "name": "...", 
                "reason": "...", 
                "dietary": "...", 
                "must_try_cuisine": "...",
                "lat": 0.00, 
                "lng": 0.00 
            }}],
            "markets": [{{ "name": "...", "reason": "..." }}],
            "traditions": {{
                "description": "...",
                "what_to_do": ["..."],
                "what_to_avoid": ["..."]
            }},
            "best_time_to_visit": {{
                "optimal_time": "...",
                "weather": "...",
                "festivals": "...",
                "footfall": "..."
            }},
            "itinerary": {{
                "schedule": "...",
                "cultural_experiences": "...",
                "local_specialties": "..."
            }},
            "safety_alerts": ["..."],
            "cautions": ["..."],
            "packing_recommendations": {{
                "cold_weather": "...",
                "beach": "...",
                "general": "..."
            }},
            "tips": [{{ "text": "...", "category": "..." }}]
        }}
        """

        try:
            original_source = ai_service.source
            ai_service.source = "groq"
            response_text = await ai_service.generate_content(prompt, system_prompt="You are an expert travel aggregation AI. Answer strictly in JSON.")
            ai_service.source = original_source
            
            # Robust JSON Extract
            clean_json = response_text
            if "```json" in response_text:
                clean_json = response_text.split("```json")[1].split("```")[0].strip()
            elif "{" in response_text:
                # Find first { and last }
                start = response_text.find("{")
                end = response_text.rfind("}")
                if start != -1 and end != -1:
                    clean_json = response_text[start:end+1]

            # Final cleanup: remove trailing commas or weird chars before parsing
            # (Basic attempt to fix minor LLM JSON flaws)
            try:
                result = json.loads(clean_json)
                # Cache for 6 hours
                await cache_service.set_cache(cache_key, result, ttl=21600)
                return result
            except json.JSONDecodeError as je:
                logger.error(f"JSON Parse Error for {location}: {je}")
                # Log a snippet of the broken JSON for debugging
                logger.debug(f"Broken JSON snippet: {clean_json[:500]}...")
                
                # Emergency fix: try to use regex to find JSON if direct extraction failed
                matches = re.findall(r'\{.*\}', response_text, re.DOTALL)
                if matches:
                    try:
                        result = json.loads(matches[-1]) # Try the largest/last match
                        return result
                    except: pass
                
                raise je

        except Exception as e:
            logger.error(f"Context reasoning completely failed for {location}: {e}")
            return {"places": [], "food": [], "markets": [], "tips": [], "error": str(e)}

    async def simple_extract(self, text: str, entity_type: str) -> List[str]:
        """
        Use Ollama for simple extraction tasks to save cost.
        """
        prompt = f"Extract all {entity_type} from the following text as a comma-separated list:\n{text}"
        
        try:
            original_source = ai_service.source
            ai_service.source = "ollama"
            response_text = await ai_service.generate_content(prompt, system_prompt="You are a data extraction AI. Return only a comma-separated list.")
            ai_service.source = original_source
            
            return [x.strip() for x in response_text.split(",") if x.strip()]
        except Exception as e:
            logger.error(f"Simple extraction failed: {e}")
            return []

context_reasoning_service = ContextReasoningService()
