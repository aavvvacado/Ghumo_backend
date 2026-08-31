from app.services.opentripmap import opentripmap
from app.services.osm_service import osm_service
import logging

logger = logging.getLogger(__name__)

class NearbyService:
    async def get_nearby_all(self, lat: float, lng: float, radius: int):
        attractions = await opentripmap.get_tourist_attractions(lat, lng, radius)
        if not isinstance(attractions, list):
            attractions = []
            
        osm_data = await osm_service.get_markets_and_transport(lat, lng, radius)
        elements = osm_data.get("elements", []) if isinstance(osm_data, dict) else []

        return {
            "restaurants": [p for p in attractions if isinstance(p, dict) and "restaurant" in p.get("kinds", "")],
            "attractions": attractions,
            "markets": [e for e in elements if "shop" in e.get("tags", {})],
            "transport": [e for e in elements if "highway" in e.get("tags", {}) or "railway" in e.get("tags", {})]
        }

nearby_service = NearbyService()
