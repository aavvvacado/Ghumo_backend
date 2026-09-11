import asyncio
import logging
from typing import Dict, Any

from app.services.osm_service import osm_service
from app.services.reddit_service import reddit_service
from app.crawlers.blog_crawler import blog_crawler
from app.services.youtube_service import youtube_service
from app.services.context_reasoning_service import context_reasoning_service
from app.services.cache_service import cache_service
from app.utils.config import settings

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
        if cached and isinstance(cached, dict):
            has_cached_content = any(len(cached.get(k, [])) > 0 for k in ["places", "food", "markets", "attractions", "hidden_gems"])
            if has_cached_content:
                return cached

        from app.database.session import SessionLocal
        from app.database.models import AIContext, Place, HiddenGem, TravelTip
        from app.services.feedback_service import feedback_service
        from app.services.place_quality_validator import place_quality_validator
        from datetime import datetime

        db = SessionLocal()
        try:
            # 2. Layer 2: Persistent AIContext (only if it has actual place intelligence)
            existing_context = db.query(AIContext).filter(AIContext.query == location_lower).first()
            if existing_context and existing_context.ai_response and isinstance(existing_context.ai_response, dict):
                res = dict(existing_context.ai_response)
                has_content = any(len(res.get(k, [])) > 0 for k in ["places", "food", "markets", "attractions", "hidden_gems"])
                if has_content:
                    existing_context.search_count = (existing_context.search_count or 0) + 1
                    existing_context.last_searched_at = datetime.utcnow()
                    db.commit()

                    res["enriching"] = False
                    # Attach feedback stats to all items
                    for cat in ["places", "food", "markets", "attractions", "hidden_gems"]:
                        if cat in res and isinstance(res[cat], list):
                            for item in res[cat]:
                                await feedback_service.attach_feedback_to_item(db, item, target_type="place")

                    if existing_context.search_count >= settings.CACHE_SEARCH_THRESHOLD:
                        await cache_service.set_cache(f"search:{location_lower}", res, ttl=settings.CACHE_TTL_SECONDS)

                    return res

            # 3. Layer 3: Specific Place / POI Matching (e.g. "kiet group of institutions")
            norm_q = place_quality_validator.normalize_place_name(location)
            matched_place = db.query(Place).filter(
                (Place.normalized_name == norm_q) |
                (Place.name.ilike(location.strip())) |
                (Place.normalized_name.ilike(f"%{norm_q}%")) |
                (Place.name.ilike(f"%{location.strip()}%"))
            ).order_by(Place.confidence_score.desc(), Place.search_count.desc()).first()

            if matched_place:
                target_city = (matched_place.city or "NCR").strip()
                logger.info(f"Query '{location}' matched place '{matched_place.name}' in city '{target_city}'")
                
                # Check if parent city has rich AIContext (e.g. "muradnagar")
                city_ctx = db.query(AIContext).filter(AIContext.query == target_city.lower()).first()
                if city_ctx and city_ctx.ai_response and isinstance(city_ctx.ai_response, dict):
                    city_res = dict(city_ctx.ai_response)
                    has_city_content = any(len(city_res.get(k, [])) > 0 for k in ["places", "food", "markets", "attractions", "hidden_gems"])
                    if has_city_content:
                        # Prioritize matched place at the front of its category
                        place_dict = {
                            "name": matched_place.name,
                            "type": matched_place.category or "attraction",
                            "category": "attractions" if (matched_place.category or "").lower() in ["college", "attraction", "monument", "ghat"] else "places",
                            "lat": matched_place.lat,
                            "lng": matched_place.lng,
                            "description": f"Featured destination in {target_city}",
                            "source": matched_place.source or "manual"
                        }
                        target_bucket = place_dict["category"]
                        if target_bucket not in city_res or not isinstance(city_res[target_bucket], list):
                            city_res[target_bucket] = []

                        # Filter out duplicate and insert at front
                        city_res[target_bucket] = [place_dict] + [
                            p for p in city_res[target_bucket]
                            if place_quality_validator.normalize_place_name(p.get("name", "")) != norm_q
                        ]

                        city_res["location"] = f"{matched_place.name}, {target_city}"
                        city_res["coordinates"] = {"lat": matched_place.lat, "lng": matched_place.lng}
                        city_res["enriching"] = False

                        # Cache and update the hollow AIContext
                        await cache_service.set_cache(f"search:{location_lower}", city_res, ttl=settings.CACHE_TTL_SECONDS)
                        if existing_context:
                            existing_context.ai_response = city_res
                            existing_context.search_count = (existing_context.search_count or 0) + 1
                            db.commit()
                        else:
                            db.add(AIContext(query=location_lower, ai_response=city_res, sources=["manual_seed"], confidence_score=1.0))
                            db.commit()
                        return city_res

            # 4. Layer 4: City / Region POI Lookup from Database
            city_places = db.query(Place).filter(
                (Place.city.ilike(f"%{location}%")) | (Place.city.ilike(f"%{normalized_location}%"))
            ).order_by(Place.search_count.desc()).limit(25).all()

            if city_places:
                db_places = []
                food_list = []
                markets_list = []
                attractions_list = []
                hidden_gems_list = []

                for p in city_places:
                    p_dict = {
                        "id": str(p.id),
                        "name": p.name,
                        "lat": p.lat,
                        "lng": p.lng,
                        "type": p.category,
                        "category": p.category,
                        "source": p.source or "db"
                    }
                    await feedback_service.attach_feedback_to_item(db, p_dict, target_type="place")
                    
                    cat = (p.category or "").lower()
                    if any(f in cat for f in ["food", "restaurant", "cafe", "dhaba"]):
                        food_list.append(p_dict)
                    elif any(m in cat for m in ["market", "bazaar"]):
                        markets_list.append(p_dict)
                    elif any(a in cat for a in ["attraction", "college", "monument", "ghat", "temple"]):
                        attractions_list.append(p_dict)
                    elif any(h in cat for h in ["gem", "hidden"]):
                        hidden_gems_list.append(p_dict)
                    else:
                        db_places.append(p_dict)

                # Fetch travel tips from DB
                tips_records = db.query(TravelTip).filter(TravelTip.city.ilike(f"%{location}%")).limit(5).all()
                tips_list = [t.tip_text for t in tips_records] if tips_records else []

                results = {
                    "location": normalized_location.title(),
                    "coordinates": {"lat": city_places[0].lat, "lng": city_places[0].lng},
                    "places": db_places,
                    "food": food_list,
                    "markets": markets_list,
                    "attractions": attractions_list,
                    "hidden_gems": hidden_gems_list,
                    "tips": tips_list,
                    "enriching": False
                }

                await cache_service.set_cache(f"search:{location_lower}", results, ttl=settings.CACHE_TTL_SECONDS)
                if existing_context:
                    existing_context.ai_response = results
                    db.commit()
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

            # 3. Batch Image Resolution for all places
            places_list = intelligence.get("places", [])
            food_list = intelligence.get("food", [])
            markets_list = intelligence.get("markets", [])
            attractions_list = intelligence.get("attractions", [])
            gems_list = intelligence.get("hidden_gems", [])

            all_place_items = places_list + food_list + markets_list + attractions_list + gems_list
            if all_place_items:
                from app.services.place_image_resolver import place_image_resolver
                try:
                    await place_image_resolver.resolve_places_batch(all_place_items, city=normalized_location, timeout=3.0)
                except Exception as img_err:
                    logger.warning(f"Image batch resolution error in enrichment for {normalized_location}: {img_err}")

            # Output Preparation
            raw_result = {
                "location": normalized_location,
                "coordinates": {"lat": lat, "lng": lng} if lat and lng else {},
                "places": places_list,
                "food": food_list,
                "markets": markets_list,
                "attractions": attractions_list,
                "hidden_gems": gems_list,
                "tips": intelligence.get("tips", []),
                "enriching": False
            }

            # Quality Validation Layer Check
            from app.services.place_quality_validator import place_quality_validator
            is_valid, val_reason, result = place_quality_validator.filter_and_validate_enrichment_response(raw_result)

            if not is_valid:
                logger.warning(f"Enrichment result rejected by PlaceQualityValidator for '{normalized_location}': {val_reason}")
                err_response = {
                    "location": normalized_location,
                    "coordinates": {},
                    "places": [], "food": [], "markets": [], "attractions": [], "hidden_gems": [], "tips": [],
                    "enriching": False,
                    "error": {
                        "code": "INSUFFICIENT_PLACE_DATA",
                        "message": "We couldn't find sufficient high-quality information for this place."
                    }
                }
                return err_response

            # 4. Save to Database & Knowledge Graph (PostgreSQL persistent source of truth)
            from app.services.knowledge_updater import knowledge_updater
            corpora = {"youtube": yt_text, "reddit": reddit_text, "blog": blog_text}
            await knowledge_updater.sync_intelligence_to_db(location_lower, result, corpora)

            # 5. Hot Cache Check
            # Only promote to Valkey hot cache if result has valid data
            has_data = bool(result.get("places") or result.get("food") or result.get("attractions") or result.get("hidden_gems"))
            if has_data:
                await cache_service.set_cache(f"search:{location_lower}", result, ttl=settings.CACHE_TTL_SECONDS)
                logger.info(f"Background enrichment completed successfully for {normalized_location}. Stored in DB and promoted to cache.")
            
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
