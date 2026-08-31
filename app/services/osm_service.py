from app.utils.http_client import safe_post_json
import logging

logger = logging.getLogger(__name__)

class OSMService:
    def __init__(self):
        self.overpass_url = "https://overpass-api.de/api/interpreter"

    async def get_nearby_places(self, lat: float, lng: float, radius: int = 10000):
        """
        Fetch nearby places from OSM and categorize them.
        """
        query = f"""
        [out:json];
        (
          node["amenity"~"restaurant|cafe|food_court|bar"](around:{radius},{lat},{lng});
          node["shop"~"market|mall|supermarket|bazaar"](around:{radius},{lat},{lng});
          way["shop"~"market|mall|supermarket|bazaar"](around:{radius},{lat},{lng});
          node["tourism"~"attraction|museum|viewpoint|monument"](around:{radius},{lat},{lng});
          way["tourism"~"attraction|museum|viewpoint|monument"](around:{radius},{lat},{lng});
          node["highway"="bus_stop"](around:{radius},{lat},{lng});
          node["railway"~"station|subway_entrance"](around:{radius},{lat},{lng});
        );
        out center;
        """
        try:
            response = await safe_post_json(self.overpass_url, data={"data": query})
            if not response or "elements" not in response:
                return []

            places = []
            for el in response["elements"]:
                tags = el.get("tags", {})
                name = tags.get("name")
                if not name: continue

                category = "other"
                if "amenity" in tags:
                    category = "restaurants" if tags["amenity"] in ["restaurant", "cafe", "food_court", "bar"] else "amenity"
                elif "shop" in tags:
                    category = "markets"
                elif "tourism" in tags:
                    category = "tourist attractions"
                elif "highway" in tags or "railway" in tags:
                    category = "transport"

                places.append({
                    "name": name,
                    "lat": el.get("lat") or el.get("center", {}).get("lat"),
                    "lng": el.get("lon") or el.get("center", {}).get("lon"),
                    "category": category,
                    "tags": tags
                })
            return places
        except Exception as e:
            logger.error(f"OSM Overpass query failed: {e}")
            return []

    async def get_markets_and_transport(self, lat: float, lng: float, radius: int = 5000):
        """
        Specialized query for markets and transport nodes.
        """
        query = f"""
        [out:json];
        (
          node["shop"~"market|mall|supermarket|bazaar"](around:{radius},{lat},{lng});
          node["highway"="bus_stop"](around:{radius},{lat},{lng});
          node["railway"~"station|subway_entrance"](around:{radius},{lat},{lng});
        );
        out body;
        """
        try:
            response = await safe_post_json(self.overpass_url, data={"data": query})
            return response if response else {"elements": []}
        except Exception as e:
            logger.error(f"OSM Markets/Transport query failed: {e}")
            return {"elements": []}

osm_service = OSMService()
