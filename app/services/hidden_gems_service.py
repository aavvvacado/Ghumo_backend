import logging
from typing import List, Dict, Any
from app.database.session import SessionLocal
from app.database.models import HiddenGem, LocalContribution
from app.services.search_service import search_service
from app.services.place_quality_validator import place_quality_validator
from app.services.place_image_resolver import place_image_resolver
from app.services.cache_service import cache_service

logger = logging.getLogger(__name__)

class HiddenGemsService:
    async def discover_gems(self, location: str) -> List[Dict[str, Any]]:
        """
        Discover hidden gems using a hybrid approach:
        1. Query cached gems from Valkey
        2. Query verified manual & captain gems directly from the PostgreSQL database
        3. Query the central intelligence engine for additional local discoveries
        4. Deduplicate collision-safely via normalized names
        5. Enrich with high-res verified images
        """
        clean_loc = location.strip().lower()
        cache_key = f"hidden_gems:{clean_loc}"
        
        cached = await cache_service.get_cache(cache_key)
        if cached and isinstance(cached, list):
            logger.info(f"Returning {len(cached)} cached hidden gems for {location}")
            return cached

        logger.info(f"Discovering hidden gems for {location} via hybrid DB + central engine...")
        seen_names = set()
        formatted_gems = []

        # 1. First priority: Verified HiddenGems from DB (seeded or curated)
        db = SessionLocal()
        try:
            db_gems = db.query(HiddenGem).filter(
                (HiddenGem.city.ilike(f"%{clean_loc}%")) | 
                (HiddenGem.name.ilike(f"%{clean_loc}%"))
            ).order_by(HiddenGem.confidence_score.desc()).all()

            for gem in db_gems:
                norm = place_quality_validator.normalize_place_name(gem.name)
                if norm and norm not in seen_names:
                    seen_names.add(norm)
                    score_val = gem.confidence_score if gem.confidence_score is not None else 0.95
                    # Scale to 1-10 if normalized between 0-1
                    scaled_score = round(score_val * 10, 1) if score_val <= 1.0 else round(score_val, 1)
                    formatted_gems.append({
                        "name": gem.name,
                        "description": f"Verified local secret in {gem.city or location} ({gem.category or 'hidden gem'})",
                        "type": gem.category or "hidden_gem",
                        "lat": gem.lat,
                        "lng": gem.lng,
                        "score": scaled_score,
                        "source": gem.source or "verified_db",
                        "city": gem.city or location
                    })

            # Also check LocalContribution (category == 'hidden_gem' or all verified contributions for location)
            contributions = db.query(LocalContribution).filter(
                LocalContribution.location.ilike(f"%{clean_loc}%"),
                LocalContribution.is_verified == 1
            ).all()
            for contrib in contributions:
                norm = place_quality_validator.normalize_place_name(contrib.name)
                if norm and norm not in seen_names:
                    seen_names.add(norm)
                    formatted_gems.append({
                        "name": contrib.name,
                        "description": contrib.description or "Local captain verified hidden gem",
                        "type": contrib.category or "hidden_gem",
                        "lat": contrib.lat,
                        "lng": contrib.lng,
                        "score": 9.2,
                        "source": f"captain_{contrib.submitted_by}",
                        "city": contrib.location
                    })
        except Exception as e:
            logger.error(f"Error fetching DB hidden gems for {location}: {e}")
        finally:
            db.close()

        # 2. Second priority: Search Service (AIContext, OSM, Central Engine)
        try:
            result = await search_service.search_all(location)
            engine_gems = result.get("hidden_gems", []) if isinstance(result, dict) else []
            for gem in engine_gems:
                name = gem.get("name")
                if not name:
                    continue
                norm = place_quality_validator.normalize_place_name(name)
                if norm and norm not in seen_names:
                    seen_names.add(norm)
                    formatted_gems.append({
                        "name": name,
                        "description": gem.get("reason") or gem.get("description") or "Discovered hidden gem",
                        "type": gem.get("type", "hidden_gem"),
                        "lat": gem.get("lat", 0.0),
                        "lng": gem.get("lng", 0.0),
                        "score": float(gem.get("score") or 9.0),
                        "source": gem.get("source", "intelligence_engine"),
                        "city": location
                    })
        except Exception as e:
            logger.error(f"Central engine hidden gems error for {location}: {e}")

        # 3. Resolve images concurrently for candidates
        if formatted_gems:
            try:
                await place_image_resolver.resolve_places_batch(formatted_gems, city=location, timeout=4.0)
            except Exception as e:
                logger.warning(f"Image resolution timed out or failed for hidden gems: {e}")

        # 4. Cache in Valkey (1 hour TTL)
        if formatted_gems:
            try:
                await cache_service.set_cache(cache_key, formatted_gems, ttl=3600)
            except Exception as e:
                logger.warning(f"Failed to cache hidden gems for {location}: {e}")

        return formatted_gems

hidden_gems_service = HiddenGemsService()
