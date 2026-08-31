import logging
import asyncio
from typing import Dict, Any, List
from app.services.osm_service import osm_service
from app.services.reddit_service import reddit_service
from app.crawlers.blog_crawler import blog_crawler
from app.services.groq_reasoning_service import groq_reasoning_service
from app.services.cache_service import cache_service
from app.services.opentripmap import opentripmap # Still needed for geocoding for now, or use OSM
from app.api.schemas import SearchResponse

logger = logging.getLogger(__name__)

class SearchService:
    async def normalize_geo_query(self, query: str) -> str:
        """
        Normalize queries for better search accuracy.
        Currently returns the query as-is, but can be extended for neighborhood-to-city mapping.
        """
        return query

    async def search_all(self, location: str) -> Dict[str, Any]:
        """
        The main coordination layer for the Travel Intelligence Engine.
        Synchronous-style results with multi-layer caching.
        """
        # Normalize the query first
        normalized_location = await self.normalize_geo_query(location)
        location_lower = normalized_location.lower()

        # 1. Layer 1: Valkey Cache
        cached = await cache_service.get_cache(f"search:{location_lower}")
        if cached:
            logger.info(f"Valkey cache hit for: {normalized_location}")
            return cached

        # 2. Layer 2: PostgreSQL / AI Context
        from app.database.session import SessionLocal
        from app.database.models import AIContext, SearchHistory
        db = SessionLocal()
        try:
            # Record search history
            db.add(SearchHistory(query=normalized_location))
            db.commit()

            # Check persistent AI context
            existing_context = db.query(AIContext).filter(AIContext.query == location_lower).first()
            if existing_context:
                logger.info(f"PostgreSQL AI context hit for: {normalized_location}")
                # Update Valkey
                await cache_service.set_cache(f"search:{location_lower}", existing_context.ai_response, ttl=86400)
                return existing_context.ai_response
        finally:
            db.close()

        # 3. Layer 3: External APIs (Gather new intelligence)
        logger.info(f"Cache miss. Gathering fresh intelligence for {normalized_location}...")
        
        # Geocode using Nominatim first for high precision
        lat, lng, parsed_name = None, None, normalized_location
        
        import httpx
        try:
            # Clean up overly formal titles that confuse Nominatim
            search_query = normalized_location.replace("Deemed to be University", "").strip()

            async with httpx.AsyncClient() as client:
                res = await client.get(
                    f"https://nominatim.openstreetmap.org/search",
                    params={"q": search_query, "format": "json", "limit": 1},
                    headers={"User-Agent": "GhumoTravelBot/1.0"}
                )
                data = res.json()
                
                # Fallback: if "bareilly rajendra nagar" fails, try "bareilly"
                if not data and " " in search_query:
                    parts = search_query.split()
                    # Try combinations to find the overarching city
                    for fb_query in [parts[0], parts[-1]]:
                        res = await client.get(
                            f"https://nominatim.openstreetmap.org/search",
                            params={"q": fb_query, "format": "json", "limit": 1},
                            headers={"User-Agent": "GhumoTravelBot/1.0"}
                        )
                        data = res.json()
                        if data:
                            logger.info(f"Nominatim fallback geocoded '{search_query}' to '{fb_query}'")
                            break
                            
                if data and len(data) > 0:
                    # Sort by importance (Nominatim provides this) to pick major cities over tiny villages
                    data.sort(key=lambda x: x.get("importance", 0), reverse=True)
                    lat = float(data[0]["lat"])
                    lng = float(data[0]["lon"])
                    parsed_name = data[0].get("display_name", location).split(",")[0]
                    logger.info(f"Top geocode for {normalized_location}: {parsed_name} ({lat}, {lng}) with importance {data[0].get('importance')}")
        except Exception as e:
            logger.warning(f"Nominatim geocoding failed for {location}: {e}")

        # Fallback to OpenTripMap if Nominatim fails
        if not lat:
            from app.services.opentripmap import opentripmap
            geo = await opentripmap.get_geoname(location)
            # Prevent incredibly wrong partial matches (like Bareilly mapping to Hyderabad)
            if not geo or "lat" not in geo or geo.get("partial_match"):
                return {"error": f"Could not find coordinates for {location}"}
            lat, lng = geo["lat"], geo["lon"]
            parsed_name = geo.get("name", location)
            
        city_name = parsed_name

        # Dynamic radius (Default 6000m)
        search_radius = 6000

        # Gather data concurrently
        from app.services.discovery_service import discovery_service
        
        osm_task = asyncio.create_task(osm_service.get_nearby_places(lat, lng, radius=search_radius))
        reddit_task = asyncio.create_task(reddit_service.search_discussions(f"{city_name} AND (travel OR local OR places)"))
        # New deep discovery task
        discovery_task = asyncio.create_task(discovery_service.discover_local_insights(city_name))

        osm_data, reddit_text, discovery_text = await asyncio.gather(osm_task, reddit_task, discovery_task)
        
        if not reddit_text:
            logger.warning(f"Reddit context empty for {city_name}")
        if not osm_data:
            logger.warning(f"OSM data empty for {city_name}")

        # 4. AI Synthesis
        intelligence = await groq_reasoning_service.synthesize_travel_data(
            city_name, osm_data, reddit_text, discovery_text
        )

        # 5. Post-process Intelligence (Data Cleanup & Type tagging)
        # 5.0 Pre-build a coordinate map from OSM data for fast lookup
        osm_coord_map = {p["name"].lower(): (p["lat"], p["lng"]) for p in osm_data if "lat" in p and "lng" in p}

        # 5.1 Programmatic Gem Fallback
        if not intelligence.get("hidden_gems") or len(intelligence.get("hidden_gems", [])) == 0:
            candidates = intelligence.get("attractions", []) + intelligence.get("markets", [])
            if candidates:
                promoted = []
                for item in candidates:
                    if any(x in item["name"].lower() for x in ["junction", "market", "temple", "gate", "chowk", "bazaar"]):
                        promoted.append(item)
                    if len(promoted) >= 2: break
                if not promoted and candidates:
                    promoted = candidates[:1]
                intelligence["hidden_gems"] = promoted
                promoted_names = [p["name"] for p in promoted]
                if "attractions" in intelligence:
                    intelligence["attractions"] = [a for a in intelligence["attractions"] if a["name"] not in promoted_names]
                if "markets" in intelligence:
                    intelligence["markets"] = [m for m in intelligence["markets"] if m["name"] not in promoted_names]

        # 5.2 Precise Coordinate Mapping & Cleanup
        for category, items in intelligence.items():
            if category in ["food", "markets", "attractions", "hidden_gems"] and isinstance(items, list):
                for item in items:
                    item["type"] = category[:-1] if category.endswith('s') else category
                    item["source"] = "intelligence_engine"
                    
                    # Try to map exact coordinates from OSM data first
                    place_name_lower = item["name"].lower()
                    if place_name_lower in osm_coord_map:
                        item["lat"], item["lng"] = osm_coord_map[place_name_lower]
                    elif "lat" not in item or not item.get("lat") or item["lat"] == 0:
                        # Fallback: Targeted geocoding for specific place
                        try:
                            # Attempting to find better coordinates specifically for this name
                            geo = await opentripmap.get_geoname(f"{item['name']} {city_name}")
                            if geo and "lat" in geo:
                                item["lat"], item["lng"] = geo["lat"], geo["lon"]
                            else:
                                # Final fallback to city center (or near it) without jitter
                                item["lat"], item["lng"] = lat, lng
                        except:
                            item["lat"], item["lng"] = lat, lng

        # 5.5 Inject Local Captain Contributions
        db = SessionLocal()
        try:
            from app.database.models import LocalContribution
            # Get verified contributions matching the city
            contributions = db.query(LocalContribution).filter(
                LocalContribution.location == location_lower,
                LocalContribution.is_verified == 1
            ).all()

            for c in contributions:
                item = {
                    "name": c.name,
                    "description": c.description,
                    "reason": c.description,
                    "type": c.category,
                    "lat": c.lat,
                    "lng": c.lng,
                    "source": "local_captain",
                    "submitted_by": c.submitted_by
                }
                
                # Append to relevant category, mapping category string to list name
                if c.category in ["food", "market", "attraction", "hidden_gem"]:
                    list_key = c.category + "s" if c.category != "food" else "food"
                    if list_key not in intelligence:
                        intelligence[list_key] = []
                    # Prepend so they show up first
                    intelligence[list_key].insert(0, item)
                elif c.category == "tip":
                    if "tips" not in intelligence:
                        intelligence["tips"] = []
                    intelligence["tips"].insert(0, {"text": c.description, "category": "local_advice", "source": "local_captain", "submitted_by": c.submitted_by})
        except Exception as e:
            logger.error(f"Failed to load local contributions for {location}: {e}")
        finally:
            db.close()

        result = {
            "location": city_name,
            "coordinates": {"lat": lat, "lng": lng},
            "food": intelligence.get("food", []),
            "markets": intelligence.get("markets", []),
            "attractions": intelligence.get("attractions", []),
            "hidden_gems": intelligence.get("hidden_gems", []),
            "tips": intelligence.get("tips", [])
        }

        # 6. Persistent Storage (Layer 2)
        db = SessionLocal()
        try:
            # Store AI context
            new_context = AIContext(
                query=location_lower,
                ai_response=result,
                sources=["osm", "reddit", "blog"],
                confidence_score=0.85
            )
            db.add(new_context)
            
            # Store in search_history is already done above
            
            # Store tips separately for the tips endpoint
            from app.database.models import TravelTip
            for tip in result["tips"]:
                db.add(TravelTip(
                    city=city_name,
                    tip_text=tip.get("text"),
                    source="intelligence_engine",
                    confidence_score=0.9
                )
            )
            db.commit()
        except Exception as e:
            logger.error(f"Error persisting search results: {e}")
        finally:
            db.close()

        # 7. Update Cache (Layer 1)
        await cache_service.set_cache(f"search:{location_lower}", result, ttl=86400)
        
        return result

search_service = SearchService()
