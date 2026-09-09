import asyncio
import logging
from typing import Dict, Any

from app.services.osm_service import osm_service
from app.services.reddit_service import reddit_service
from app.crawlers.blog_crawler import blog_crawler
from app.services.youtube_service import youtube_service
from app.services.context_reasoning_service import context_reasoning_service
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class EnrichmentService:
    async def get_fast_results(self, location: str) -> Dict[str, Any]:
        """
        Quick check in Valkey cache and DB for existing intelligence.
        Now includes a DB lookup for nearby places if cache is missed.
        """
        from app.services.search_service import search_service
        normalized_location = await search_service.normalize_geo_query(location)
        location_lower = normalized_location.lower()
        
        # 1. Layer 1: Valkey Cache (Instant)
        cached = await cache_service.get_cache(f"search:{location_lower}")
        if cached:
            return cached

        from app.database.session import SessionLocal
        from app.database.models import AIContext, Place
        db = SessionLocal()
        try:
            existing_context = db.query(AIContext).filter(AIContext.query == location_lower).first()
            if existing_context:
                res = existing_context.ai_response
                if not res.get("places") and not res.get("hidden_gems"):
                    res["enriching"] = True
                await cache_service.set_cache(f"search:{location_lower}", res, ttl=86400)
                return res
            
            # Layer 3: Local POI Lookup (Fast DB Search)
            # If no context, look for places directly in the DB that match the city
            recent_places = db.query(Place).filter(Place.city.ilike(f"%{location}%")).limit(20).all()
            if recent_places:
                results = {
                    "location": normalized_location,
                    "coordinates": {"lat": recent_places[0].lat, "lng": recent_places[0].lng},
                    "places": [{"name": p.name, "lat": p.lat, "lng": p.lng, "type": p.category, "source": "db"} for p in recent_places],
                    "food": [], "markets": [], "attractions": [], "hidden_gems": [], "tips": [],
                    "enriching": True
                }
                await cache_service.set_cache(f"search:{location_lower}", results, ttl=300)
                return results
        finally:
            db.close()

        # If perfectly empty, we return a structural skeleton so the UI doesn't crash
        # and we let the enrichment job fill it soon.
        return {
            "location": normalized_location,
            "coordinates": {},
            "places": [],
            "food": [],
            "markets": [],
            "attractions": [],
            "hidden_gems": [],
            "tips": [],
            "enriching": True  # Flag to let UI know data is coming soon
        }

    async def run_enrichment_job(self, location: str, lat: float = None, lng: float = None):
        """
        Fetches heavy data from YouTube, Reddit, Blogs, and OSM.
        Reasons with Groq and then triggers DB updates.
        """
        from app.services.search_service import search_service
        normalized_location = await search_service.normalize_geo_query(location)
        logger.info(f"Starting background enrichment for {normalized_location}...")
        location_lower = normalized_location.lower()
        
        # 0. Geocode if coordinates are missing
        if not lat or not lng:
            logger.info(f"Coordinates missing for {normalized_location}. Geocoding first...")
            import httpx
            try:
                # Setup common geocoding function
                async def fetch_coords(q):
                    async with httpx.AsyncClient() as client:
                        res = await client.get(
                            "https://nominatim.openstreetmap.org/search",
                            params={"q": q, "format": "json", "limit": 3, "countrycodes": "in"},
                            headers={"User-Agent": "GhumoTravelBot/1.0"}
                        )
                        data = res.json()
                        if not data:
                            res = await client.get(
                                "https://nominatim.openstreetmap.org/search",
                                params={"q": f"{q}, India", "format": "json", "limit": 3},
                                headers={"User-Agent": "GhumoTravelBot/1.0"}
                            )
                            data = res.json()
                        if not data:
                            res = await client.get(
                                "https://nominatim.openstreetmap.org/search",
                                params={"q": q, "format": "json", "limit": 3},
                                headers={"User-Agent": "GhumoTravelBot/1.0"}
                            )
                            data = res.json()
                        return data

                # Clean query
                clean_q = normalized_location.replace("Phase", "").replace("Sector", "").strip()
                data = await fetch_coords(normalized_location)
                
                if not data and normalized_location != clean_q:
                    data = await fetch_coords(clean_q)

                # Token fallback
                if not data and " " in normalized_location:
                    parts = normalized_location.split()
                    # Try city (often the last part)
                    city_candidate = parts[-1]
                    logger.info(f"Trying city fallback geocoding for: {city_candidate}")
                    data = await fetch_coords(city_candidate) # Fixed: use city_candidate

                if data:
                    # Sort by importance
                    data.sort(key=lambda x: x.get("importance", 0), reverse=True)
                    lat = float(data[0]["lat"])
                    lng = float(data[0]["lon"])
                    logger.info(f"SUCCESS: Geocoded {normalized_location} to {lat}, {lng} (Importance: {data[0].get('importance')})")
                else:
                    logger.warning(f"FAILURE: Geocoding failed for {normalized_location} after fallbacks.")
                    # Final fallback to OTM
                    from app.services.opentripmap import opentripmap
                    geo = await opentripmap.get_geoname(normalized_location)
                    if not geo or "lat" not in geo:
                        # Try only the last word (likely the city)
                        geo = await opentripmap.get_geoname(normalized_location.split()[-1])
                    
                    if geo and "lat" in geo:
                        lat, lng = geo["lat"], geo["lon"]
                        logger.info(f"Fallback OTM geocoded to {lat}, {lng}")
                    else:
                        # ULTIMATE Fallback: Major Indian Cities
                        city_map = {
                            "delhi": (28.6139, 77.2090),
                            "lucknow": (26.8467, 80.9462),
                            "mumbai": (19.0760, 72.8777),
                            "bengaluru": (12.9716, 77.5946),
                            "kolkata": (22.5726, 88.3639)
                        }
                        for city_tag, coords in city_map.items(): # Fixed name to city_tag
                            if city_tag in location_lower:
                                lat, lng = coords
                                logger.info(f"Ultimate Fallback mapping to {city_tag} coords: {lat}, {lng}")
                                break

                # Update cache with coords early
                if lat and lng:
                    current_cache = await cache_service.get_cache(f"search:{location_lower}") or {}
                    current_cache.update({
                        "location": normalized_location,
                        "coordinates": {"lat": lat, "lng": lng},
                        "enriching": True
                    })
                    await cache_service.set_cache(f"search:{location_lower}", current_cache, ttl=300)

            except Exception as geode_err:
                logger.error(f"Geocoding error for {normalized_location}: {geode_err}")

        # 1. Fetch concurrent data streams
        # Using query expansion techniques
        search_radius = 8000
        
        try:
            # Gather OSM data (if we have coordinates, else approximate it)
            osm_task = asyncio.create_task(osm_service.get_nearby_places(lat, lng, radius=search_radius)) if lat and lng else None
            if not osm_task:
                logger.warning(f"Skipping OSM search for {normalized_location} due to missing coordinates.")
            
            # For query expansion, search Reddit & YouTube with different targeted suffixes
            reddit_task = asyncio.create_task(reddit_service.search_discussions(f"{normalized_location} (travel OR food OR hidden gems OR places to visit)"))
            blog_task = asyncio.create_task(blog_crawler.scrape_blogs(normalized_location))
            yt_task = asyncio.create_task(youtube_service.search_videos(normalized_location))
            
            from app.crawlers.cloudflare_crawler import cloudflare_crawler
            cloudflare_task = asyncio.create_task(cloudflare_crawler.scrape_travel_data(normalized_location))

            osm_data = []
            if osm_task:
                try:
                    osm_data = await asyncio.wait_for(osm_task, timeout=15.0)
                    logger.info(f"OSM found {len(osm_data)} places near {lat}, {lng}")
                except asyncio.TimeoutError:
                    logger.warning(f"OSM task timed out for {normalized_location}. Proceeding without map data.")
                except Exception as e:
                    logger.error(f"OSM task failed: {e}")

            # Gather data concurrently
            reddit_text, blog_text, yt_text, cf_text = await asyncio.gather(reddit_task, blog_task, yt_task, cloudflare_task)

            # Update cache with Milestone 1: Physical Scan Complete
            aligned_places = []
            if osm_data:
                # Align OSM data with final schema for consistent UI
                for p in osm_data[:12]:
                    aligned_places.append({
                        "name": p.get("name"),
                        "description": f"Located in {normalized_location}. Tagged as {p.get('category')}.",
                        "lat": p.get("lat"),
                        "lng": p.get("lng"),
                        "type": p.get("category", "attraction")[:-1] if p.get("category", "").endswith("s") else p.get("category"),
                        "ticket_price": "Checking...",
                        "timings": "Open",
                        "source": "osm_early"
                    })

            # Always update cache here so polling knows we've progressed past OSM
            await cache_service.set_cache(f"search:{location_lower}", {
                "location": normalized_location,
                "coordinates": {"lat": lat, "lng": lng} if lat and lng else {},
                "places": aligned_places,
                "enriching": True,
                "food": [], "markets": [], "hidden_gems": [], "tips": [],
                "milestone": "physical_scan_complete"
            }, ttl=300)

            # 2. AI Reasoning
            intelligence = await context_reasoning_service.synthesize_travel_data(
                location=normalized_location,
                osm_data=osm_data,
                reddit_text=reddit_text,
                blog_text=blog_text,
                youtube_text=yt_text,
                deep_scraped_text=cf_text
            )
            
            # 2.1 Fallback if Intelligence is too thin (e.g. no places found)
            if not intelligence.get("places") and not intelligence.get("food"):
                logger.info(f"Thin context for {normalized_location}. Requesting general knowledge fallback.")
                # We reuse the service but with a "allow_general_knowledge" flag in prompt implicitly
                intelligence = await context_reasoning_service.synthesize_travel_data(
                    location=normalized_location,
                    osm_data=osm_data,
                    reddit_text="FALLBACK: Use your internal knowledge of India tourism.",
                    blog_text="",
                    youtube_text="",
                    deep_scraped_text=""
                )

            # 3. Output Preparation
            result = {
                "location": normalized_location,
                "coordinates": {"lat": lat, "lng": lng} if lat and lng else {},
                "places": intelligence.get("places", []),
                "food": intelligence.get("food", []),
                "markets": intelligence.get("markets", []),
                "attractions": intelligence.get("attractions", []),
                "hidden_gems": intelligence.get("hidden_gems", []),
                "tips": intelligence.get("tips", []),
                "enriching": False
            }

            # 4. Save to Database & Knowledge Graph (Phase 4 connection point)
            from app.services.knowledge_updater import knowledge_updater
            corpora = {"youtube": yt_text, "reddit": reddit_text, "blog": blog_text}
            await knowledge_updater.sync_intelligence_to_db(location_lower, result, corpora)

            # 5. Update Cache
            has_data = bool(result.get("places") or result.get("food") or result.get("attractions") or result.get("hidden_gems"))
            ttl = 86400 if has_data else 10
            await cache_service.set_cache(f"search:{location_lower}", result, ttl=ttl)
            if has_data:
                logger.info(f"Background enrichment completed successfully for {normalized_location}.")
            else:
                logger.warning(f"Background enrichment yielded shallow data for {normalized_location}. Short cache TTL applied.")
            
            return result

        except Exception as e:
            logger.error(f"Enrichment task failed for {location}: {e}")
            # Ensure we don't leave the user hanging with 'enriching: True'
            try:
                await cache_service.set_cache(f"search:{location_lower}", {
                    "location": normalized_location,
                    "coordinates": {"lat": lat, "lng": lng} if lat and lng else {},
                    "places": [], "food": [], "markets": [],
                    "attractions": [], "hidden_gems": [], "tips": [],
                    "enriching": False, "error": str(e)
                }, ttl=600)
            except:
                pass
            return None

enrichment_service = EnrichmentService()
