from app.services.ai_service import ai_service
from app.services.search_service import search_service
import logging

logger = logging.getLogger(__name__)

class ItineraryService:
    async def generate_itinerary(self, location: str, time_available: str, interests: list, budget: str):
        # 1. Fetch data for the location
        data = await search_service.search_all(location)
        
        # 2. Extract key details
        attractions = [a["name"] for a in data.get("attractions", [])[:8]]
        restaurants = [r["name"] for r in data.get("restaurants", [])[:5]]
        markets = [m["name"] for m in data.get("markets", [])[:5]]
        
        # 3. Format a detailed prompt for Groq/AI
        prompt = (
            f"Create a detailed travel itinerary for {location}.\n"
            f"Duration: {time_available}\n"
            f"Interests: {', '.join(interests)}\n"
            f"Budget Level: {budget}\n\n"
        )
        
        has_local_data = len(attractions) > 0 or len(restaurants) > 0 or len(markets) > 0
        
        if has_local_data:
            prompt += "Please strongly prioritize using the provided exact places below:\n"
            if attractions: prompt += f"Available Attractions to include: {', '.join(attractions)}\n"
            if restaurants: prompt += f"Recommended Food/Dining: {', '.join(restaurants)}\n"
            if markets: prompt += f"Shopping/Markets: {', '.join(markets)}\n\n"
        else:
            prompt += "No verified local database places found for this exact area. Please use your internal knowledge to suggest highly accurate, real-world, famous, and hidden locations in this specific area. Do not invent names.\n\n"
            
        prompt += (
            "Format the response with a clear header for each day and use bullet points for activities. "
            "Keep it vibrant and practical."
        )
        
        system_prompt = "You are a world-class travel planner. Create highly engaging and efficient itineraries."

        # 4. Generate the itinerary
        itinerary_text = await ai_service.generate_content(prompt, system_prompt)

        # 5. Return structured response
        return {
            "location": location,
            "itinerary": itinerary_text,
            "recommended_places": (data.get("restaurants", []) + data.get("markets", []))[:10],
            "recommended_attractions": data.get("attractions", [])[:10]
        }

itinerary_service = ItineraryService()
