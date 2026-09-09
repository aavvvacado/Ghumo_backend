import httpx
import asyncio
import logging
import re
import urllib.parse
from typing import Optional, Dict, Any, List
from app.services.cache_service import cache_service
from app.utils.config import settings

logger = logging.getLogger(__name__)

def slugify(text: str) -> str:
    """Normalize string for collision-safe cache keys"""
    if not text:
        return ""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    return re.sub(r'[\s_-]+', '_', text)

class WikimediaProvider:
    """Primary free image provider using Wikidata and Wikimedia Commons APIs"""
    USER_AGENT = "GhumoTravelBot/1.0 (https://ghumo.app; contact@ghumo.app)"

    @classmethod
    async def resolve_image(cls, place_name: str, city: str = "", country: str = "India") -> Optional[Dict[str, Any]]:
        if not place_name:
            return None
        
        headers = {"User-Agent": cls.USER_AGENT}

        # Strategy 1: Wikimedia Commons Direct Media Search (Fast single HTTP call)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                query = f"{place_name} {city}".strip()
                res = await client.get(
                    "https://commons.wikimedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": query,
                        "gsrnamespace": 6,
                        "gsrlimit": 1,
                        "prop": "imageinfo",
                        "iiprop": "url|extmetadata|user",
                        "iiurlwidth": 1000,
                        "format": "json"
                    },
                    headers=headers
                )
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for _, v in pages.items():
                        imageinfo = v.get("imageinfo", [])
                        if imageinfo:
                            info = imageinfo[0]
                            url = info.get("thumburl") or info.get("url")
                            if url:
                                metadata = info.get("extmetadata", {})
                                license_meta = metadata.get("LicenseShortName", {}).get("value", "CC BY-SA")
                                user = info.get("user", "Wikimedia Contributor")
                                return {
                                    "url": url,
                                    "source": "wikimedia",
                                    "attribution": f"Photo by {user} ({license_meta}) via Wikimedia Commons"
                                }
        except Exception as e:
            logger.debug(f"Commons direct search failed for {place_name}: {e}")

        # Strategy 2: Wikipedia PageImages Search (Fast single HTTP call)
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                query = f"{place_name} {city}".strip()
                res = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "generator": "search",
                        "gsrsearch": query,
                        "gsrlimit": 1,
                        "prop": "pageimages|info",
                        "piprop": "thumbnail",
                        "pithumbsize": 1000,
                        "inprop": "url",
                        "format": "json"
                    },
                    headers=headers
                )
                if res.status_code == 200:
                    pages = res.json().get("query", {}).get("pages", {})
                    for _, v in pages.items():
                        thumb = v.get("thumbnail", {}).get("source")
                        title = v.get("title")
                        if thumb:
                            return {
                                "url": thumb,
                                "source": "wikimedia",
                                "attribution": f"Wikimedia Commons / Wikipedia ({title})"
                            }
        except Exception as e:
            logger.debug(f"Wikipedia PageImages resolution failed for {place_name}: {e}")

        # Strategy 3: Wikidata Entity Claim P18 (Fallback)
        search_query = f"{place_name} {city}".strip()
        wikidata_url = "https://www.wikidata.org/w/api.php"
        
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(
                    wikidata_url,
                    params={
                        "action": "wbsearchentities",
                        "search": search_query,
                        "language": "en",
                        "format": "json",
                        "limit": 3
                    },
                    headers=headers
                )
                if res.status_code == 200:
                    search_data = res.json()
                    entities = search_data.get("search", [])
                    if entities:
                        entity_ids = [e["id"] for e in entities if "id" in e]
                        claims_res = await client.get(
                            wikidata_url,
                            params={
                                "action": "wbgetentities",
                                "ids": "|".join(entity_ids),
                                "props": "claims",
                                "format": "json"
                            },
                            headers=headers
                        )
                        if claims_res.status_code == 200:
                            claims_data = claims_res.json().get("entities", {})
                            image_filename = None
                            for qid in entity_ids:
                                entity_claims = claims_data.get(qid, {}).get("claims", {})
                                if "P18" in entity_claims:
                                    p18_claims = entity_claims["P18"]
                                    if p18_claims and "mainsnak" in p18_claims[0]:
                                        image_filename = p18_claims[0]["mainsnak"]["datavalue"]["value"]
                                        break
                            
                            if image_filename:
                                commons_url = "https://commons.wikimedia.org/w/api.php"
                                img_res = await client.get(
                                    commons_url,
                                    params={
                                        "action": "query",
                                        "titles": f"File:{image_filename}",
                                        "prop": "imageinfo",
                                        "iiprop": "url|extmetadata|user",
                                        "format": "json"
                                    },
                                    headers=headers
                                )
                                if img_res.status_code == 200:
                                    pages = img_res.json().get("query", {}).get("pages", {})
                                    for _, page in pages.items():
                                        imageinfo = page.get("imageinfo", [])
                                        if imageinfo:
                                            info = imageinfo[0]
                                            direct_url = info.get("url")
                                            if direct_url:
                                                metadata = info.get("extmetadata", {})
                                                license_meta = metadata.get("LicenseShortName", {}).get("value", "CC BY-SA")
                                                user = info.get("user", "Wikimedia Contributor")
                                                return {
                                                    "url": direct_url,
                                                    "source": "wikimedia",
                                                    "attribution": f"Photo by {user} ({license_meta}) via Wikimedia Commons"
                                                }
        except Exception as e:
            logger.debug(f"Wikidata resolution failed for {place_name}: {e}")

        return None


class UnsplashProvider:
    """Fallback travel photography provider via Unsplash API"""
    
    @classmethod
    async def resolve_image(cls, place_name: str, city: str = "") -> Optional[Dict[str, Any]]:
        access_key = settings.UNSPLASH_ACCESS_KEY
        if not access_key:
            return None

        query = f"{place_name} {city}".strip()
        url = "https://api.unsplash.com/search/photos"
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    url,
                    params={"query": query, "per_page": 1, "client_id": access_key}
                )
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    if results:
                        photo = results[0]
                        photo_url = photo.get("urls", {}).get("regular") or photo.get("urls", {}).get("small")
                        photographer = photo.get("user", {}).get("name", "Unsplash Photographer")
                        
                        if photo_url:
                            return {
                                "url": photo_url,
                                "source": "unsplash",
                                "attribution": f"Photo by {photographer} on Unsplash"
                            }
        except Exception as e:
            logger.debug(f"Unsplash resolution failed for {place_name}: {e}")

        return None


class GooglePlacesProvider:
    """Optional fallback provider using Google Places Photos"""

    @classmethod
    async def resolve_image(cls, place_name: str, city: str = "") -> Optional[Dict[str, Any]]:
        api_key = settings.GOOGLE_PLACES_API_KEY
        if not api_key:
            return None

        query = f"{place_name} {city}".strip()
        search_url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
        
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get(
                    search_url,
                    params={
                        "input": query,
                        "inputtype": "textquery",
                        "fields": "photos",
                        "key": api_key
                    }
                )
                if res.status_code == 200:
                    candidates = res.json().get("candidates", [])
                    if candidates and "photos" in candidates[0]:
                        photo_ref = candidates[0]["photos"][0].get("photo_reference")
                        if photo_ref:
                            photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photo_reference={photo_ref}&key={api_key}"
                            return {
                                "url": photo_url,
                                "source": "google_places",
                                "attribution": "Google Places Photos"
                            }
        except Exception as e:
            logger.debug(f"Google Places photo resolution failed for {place_name}: {e}")

        return None


class PlaceImageResolver:
    """
    Unified Image Resolution Engine.
    Handles caching, multi-provider fallbacks, disambiguation, and concurrent batch resolution.
    """

    @staticmethod
    def get_cache_key(place_name: str, city: str = "", country: str = "India") -> str:
        p_slug = slugify(place_name)
        c_slug = slugify(city)
        cntry_slug = slugify(country)
        return f"image:{p_slug}:{c_slug}:{cntry_slug}"

    async def resolve_place_image(self, place_name: str, city: str = "", country: str = "India", timeout: float = 6.0) -> Optional[Dict[str, Any]]:
        """
        Resolve a single place image using cache -> Wikimedia -> Unsplash -> Google Places.
        """
        if not place_name:
            return None

        cache_key = self.get_cache_key(place_name, city, country)
        
        # 1. Check Valkey Cache
        try:
            cached = await cache_service.get_cache(cache_key)
            if cached is not None:
                return cached.get("image") if isinstance(cached, dict) else cached
        except Exception as cache_err:
            logger.debug(f"Cache check error for {place_name}: {cache_err}")

        # Helper to execute resolution with timeout
        async def _execute_providers():
            # Provider 1: Wikimedia / Wikidata
            image_data = await WikimediaProvider.resolve_image(place_name, city, country)
            if image_data:
                return image_data

            # Provider 2: Unsplash
            image_data = await UnsplashProvider.resolve_image(place_name, city)
            if image_data:
                return image_data

            # Provider 3: Google Places
            image_data = await GooglePlacesProvider.resolve_image(place_name, city)
            if image_data:
                return image_data

            return None

        image_result = None
        try:
            image_result = await asyncio.wait_for(_execute_providers(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Image resolution timed out after {timeout}s for {place_name}")
            image_result = None
        except Exception as err:
            logger.error(f"Image resolution error for {place_name}: {err}")
            image_result = None

        # Cache result (7 days for valid image, 1 hour for None)
        ttl = 604800 if image_result else 3600
        try:
            await cache_service.set_cache(cache_key, {"image": image_result}, ttl=ttl)
        except Exception:
            pass

        return image_result

    async def resolve_places_batch(self, places: List[Dict[str, Any]], city: str = "", country: str = "India", timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Concurrently enrich a list of place dictionaries with an 'image' field in-place.
        Guaranteed non-blocking: Never raises exceptions or crashes calling response.
        """
        if not places:
            return places

        async def _resolve_item(place: Dict[str, Any]):
            if not isinstance(place, dict):
                return place
            
            existing_img = place.get("image")
            if isinstance(existing_img, dict) and existing_img.get("url"):
                return place

            name = place.get("name") or place.get("place")
            if not name:
                place["image"] = None
                return place

            item_city = place.get("city") or city
            try:
                img_info = await self.resolve_place_image(name, city=item_city, country=country, timeout=timeout)
                place["image"] = img_info
            except Exception as e:
                logger.debug(f"Failed to resolve image for batch item {name}: {e}")
                place["image"] = None
            return place

        tasks = [_resolve_item(p) for p in places]
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Batch image resolution gather failed: {e}")

        return places

place_image_resolver = PlaceImageResolver()
