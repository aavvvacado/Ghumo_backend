import logging
from app.services.search_service import search_service

logger = logging.getLogger(__name__)

class HiddenGemsService:
    async def discover_gems(self, location: str):
        """
        Discover hidden gems using the central engine to guarantee 
        strict geographic bounds, accurate coordinates, and caching.
        """
        logger.info(f"Discovering hidden gems for {location} via central engine...")
        try:
            result = await search_service.search_all(location)
            if "error" in result:
                logger.error(f"Central engine returned error: {result['error']}")
                return []
                
            gems = result.get("hidden_gems", [])
            formatted_gems = []
            
            for gem in gems:
                formatted_gems.append({
                    "name": gem.get("name", "Unknown Gem"),
                    "description": gem.get("reason", gem.get("description", "Discovered hidden gem")),
                    "type": gem.get("type", "hidden_gem"),
                    "lat": gem.get("lat", 0.0), # The central engine handles fallbacks now
                    "lng": gem.get("lng", 0.0),
                    "score": 9.0,
                    "source": gem.get("source", "intelligence_engine")
                })
                
            return formatted_gems
        except Exception as e:
            logger.error(f"Failed to discover hidden gems for {location}: {e}")
            return []

hidden_gems_service = HiddenGemsService()
