from app.utils.http_client import safe_get_json
from app.utils.config import settings

class OpenTripMapService:
    def __init__(self):
        self.api_key = settings.OPENTRIPMAP_API_KEY
        self.base_url = "https://api.opentripmap.com/0.1/en"

    async def get_tourist_attractions(self, lat: float, lng: float, radius: int, kinds: str = "interesting_places"):
        return await safe_get_json(
            f"{self.base_url}/places/radius",
            params={
                "radius": radius,
                "lon": lng,
                "lat": lat,
                "kinds": kinds,
                "format": "json",
                "apikey": self.api_key
            }
        )

    async def get_place_xid(self, xid: str):
        return await safe_get_json(
            f"{self.base_url}/places/xid/{xid}",
            params={"apikey": self.api_key}
        )

    async def get_geoname(self, name: str):
        return await safe_get_json(
            f"{self.base_url}/places/geoname",
            params={"name": name, "apikey": self.api_key}
        )

opentripmap = OpenTripMapService()
