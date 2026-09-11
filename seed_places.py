import os
import json
import argparse
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from app.database.session import SessionLocal, engine, sync_db_sequences
from app.database.models import Base, Place, HiddenGem, AIContext, TravelTip
from app.services.place_quality_validator import PlaceQualityValidator
from app.services.cache_service import cache_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_places")

CATEGORY_MAP = {
    "attraction": "attractions",
    "attractions": "attractions",
    "food": "food",
    "restaurant": "food",
    "cafe": "food",
    "market": "markets",
    "markets": "markets",
    "bazaar": "markets",
    "hidden_gem": "hidden_gems",
    "hidden_gems": "hidden_gems",
    "gem": "hidden_gems",
    "places": "places",
    "place": "places"
}

def load_places_file(file_path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if not isinstance(data, list):
        raise ValueError("Root element of JSON must be a list of place objects.")
    
    return data

async def seed_places(file_path: str, sync_cache: bool = True):
    logger.info(f"Connecting to database...")
    Base.metadata.create_all(bind=engine)
    sync_db_sequences()

    raw_items = load_places_file(file_path)
    logger.info(f"Loaded {len(raw_items)} items from {file_path}")

    db = SessionLocal()
    inserted_count = 0
    updated_count = 0
    skipped_count = 0
    file_dup_count = 0
    gems_count = 0
    tips_count = 0

    # Intra-file deduplication tracker: (norm_name, city_norm)
    seen_in_seed: set = set()

    # Grouped intelligence cache for fast instant search
    city_buckets: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}

    try:
        for idx, item in enumerate(raw_items, 1):
            is_valid, reason, clean_item = PlaceQualityValidator.validate_place_item(item)
            if not is_valid:
                logger.warning(f"Row {idx} skipped: {reason} -> {item.get('name')}")
                skipped_count += 1
                continue

            name = clean_item.get("name", "").strip()
            city = (clean_item.get("city") or "NCR").strip()
            category_raw = clean_item.get("category") or clean_item.get("type") or "places"
            cat_group = CATEGORY_MAP.get(category_raw.lower(), "places")
            place_type = clean_item.get("type") or cat_group

            lat = float(clean_item.get("lat", 0.0))
            lng = float(clean_item.get("lng", 0.0))
            desc = clean_item.get("description", "")
            source = clean_item.get("source", "manual")
            norm_name = PlaceQualityValidator.normalize_place_name(name)
            city_norm = city.lower()

            # 0. Check intra-file duplicate
            seed_key = (norm_name, city_norm)
            if seed_key in seen_in_seed:
                logger.info(f"Duplicate in seed file detected: '{name}' in {city} (keeping first instance).")
                file_dup_count += 1
                continue
            seen_in_seed.add(seed_key)

            # 1. Check existing place in DB (Conflict Resolution)
            existing_place = db.query(Place).filter(
                (
                    (Place.normalized_name == norm_name) |
                    (Place.name.ilike(name)) |
                    (Place.normalized_name.ilike(f"%{norm_name}%")) |
                    (Place.name.ilike(f"%{name}%"))
                ) & (Place.city.ilike(f"%{city}%") | Place.city.ilike(f"%NCR%"))
            ).first()

            ext_id = f"manual_{norm_name.replace(' ', '_')}_{city_norm}"

            if not existing_place:
                # INSERT: Brand new place with baseline search count boost
                place_record = Place(
                    external_id=ext_id,
                    name=name,
                    normalized_name=norm_name,
                    category=place_type,
                    lat=lat,
                    lng=lng,
                    city=city,
                    source=source,
                    confidence_score=1.0,
                    source_count=1,
                    search_count=5,  # Boosted for /suggestions
                    created_at=datetime.utcnow()
                )
                db.add(place_record)
                db.flush()
                inserted_count += 1
                logger.debug(f"[INSERT] Added new place: {name} ({city})")
                current_place_id = place_record.id
            else:
                # RESOLVE CONFLICT (UPDATE): Upgrade existing place with verified manual data
                logger.info(f"[RESOLVE CONFLICT] Updating existing record '{existing_place.name}' (ID: {existing_place.id}) with manual data -> '{name}'")
                existing_place.name = name
                existing_place.normalized_name = norm_name
                existing_place.lat = lat
                existing_place.lng = lng
                existing_place.category = place_type
                existing_place.source = "manual"
                existing_place.confidence_score = 1.0
                existing_place.source_count = (existing_place.source_count or 1) + 1
                existing_place.search_count = max(existing_place.search_count or 1, 5)
                updated_count += 1
                current_place_id = existing_place.id

            # 2. If it's a hidden gem or authentic student spot, also upsert into `hidden_gems` table
            is_gem = (cat_group == "hidden_gems") or (place_type in ["street_food", "hangout"]) or (place_type in ["cafe", "fast_food"] and ("kiet" in desc.lower() or "pillar" in desc.lower() or "hostel" in desc.lower()))
            if is_gem:
                existing_gem = db.query(HiddenGem).filter(
                    (HiddenGem.name.ilike(name) | (HiddenGem.name.ilike(f"%{name}%"))) &
                    (HiddenGem.city.ilike(f"%{city}%"))
                ).first()
                if not existing_gem:
                    db.add(HiddenGem(
                        name=name,
                        category=place_type,
                        lat=lat,
                        lng=lng,
                        city=city,
                        source=source,
                        confidence_score=1.0,
                        created_at=datetime.utcnow()
                    ))
                    gems_count += 1
                else:
                    existing_gem.lat = lat
                    existing_gem.lng = lng
                    existing_gem.confidence_score = 1.0

            # 2.5 Index TravelTip for this place if description is substantial
            if desc and len(desc) >= 15:
                tip_text = f"{name}: {desc}"
                existing_tip = db.query(TravelTip).filter(
                    (TravelTip.city.ilike(f"%{city}%")) & (TravelTip.tip_text == tip_text)
                ).first()
                if not existing_tip:
                    db.add(TravelTip(
                        place_id=current_place_id,
                        city=city,
                        tip_text=tip_text,
                        source="manual",
                        confidence_score=1.0,
                        created_at=datetime.utcnow()
                    ))
                    tips_count += 1

            # 3. Add to city grouping for instant AIContext synthesis
            if city_norm not in city_buckets:
                city_buckets[city_norm] = {
                    "places": [], "food": [], "markets": [],
                    "attractions": [], "hidden_gems": [], "tips": []
                }
            
            clean_item_dict = {
                "name": name,
                "type": place_type,
                "category": cat_group,
                "lat": lat,
                "lng": lng,
                "description": desc,
                "source": source
            }
            city_buckets[city_norm][cat_group].append(clean_item_dict)
            if is_gem and clean_item_dict not in city_buckets[city_norm]["hidden_gems"]:
                city_buckets[city_norm]["hidden_gems"].append(clean_item_dict)

        CITY_TIPS = {
            "muradnagar": [
                "KIET Back Gate has student food stalls open until late night with great cheese maggi and chai.",
                "Chhota Haridwar on the Upper Ganga Canal is best visited around sunset for evening aarti and serene ghat walks.",
                "Duhai RRTS station (Namo Bharat) connects Muradnagar to Ghaziabad and Delhi in under 20 minutes."
            ],
            "ghaziabad": [
                "Raj Nagar District Centre (RDC) is Ghaziabad's premier hub for evening dining, cafes, and street food.",
                "Indirapuram Habitat Centre and Shipra Mall offer great weekend shopping, dining, and family entertainment.",
                "City Forest along Hindon Riverfront is an ideal morning jogging and green nature trail."
            ],
            "modinagar": [
                "Modi Mandir (Shri Laxmi Narayan Temple) is the iconic landmark of Modinagar with expansive gardens and lotus ponds.",
                "Modinagar South and Modinagar North Namo Bharat RRTS stations provide high-speed transit directly to Delhi and Meerut.",
                "Rukmani Market near the railway station is the primary destination for local clothing, dupattas, and footwear."
            ],
            "noida": [
                "Sector 18 Atta Market is Noida's top street shopping and electronics destination (some stores closed Mondays).",
                "Brahmaputra Market (Sector 29) is renowned for night street food, rolls, and momos.",
                "Advant Navis in Sector 142 offers upscale cafes and evening rooftop dining overlooking the expressway."
            ],
            "greater noida": [
                "Knowledge Park has multiple budget student food courts and late-night hangouts catering to university campuses.",
                "Pari Chowk is the central landmark connecting commercial complexes, metro, and the Yamuna Expressway."
            ],
            "delhi": [
                "Chandni Chowk and Old Delhi markets are best explored by walking or e-rickshaws via Chandni Chowk Metro Station.",
                "Hauz Khas Village combines historic 13th-century ruins and Deer Park with trendy rooftop cafes.",
                "Majnu Ka Tilla (Tibetan Colony) near North Campus is famous for thukpa, momos, and serene monastery lanes."
            ]
        }

        # Index city-wide tips
        for c_key, t_list in CITY_TIPS.items():
            for t_str in t_list:
                existing_c_tip = db.query(TravelTip).filter(
                    (TravelTip.city.ilike(f"%{c_key}%")) & (TravelTip.tip_text == t_str)
                ).first()
                if not existing_c_tip:
                    db.add(TravelTip(
                        city=c_key.title(),
                        tip_text=t_str,
                        source="manual",
                        confidence_score=1.0,
                        created_at=datetime.utcnow()
                    ))
                    tips_count += 1

        db.commit()
        logger.info(f"Database sync summary: {inserted_count} new places inserted, {updated_count} existing places updated, {gems_count} hidden gems, {tips_count} travel tips indexed, {file_dup_count} duplicates skipped.")

        # 4. Synthesize AIContext for each city bucket with Smart Merge
        for city_key, bucket in city_buckets.items():
            city_title = city_key.title()
            existing_ctx = db.query(AIContext).filter(AIContext.query == city_key).first()

            # Smart merge with existing intelligence if available
            merged_bucket = {cat: list(bucket[cat]) for cat in ["places", "food", "markets", "attractions", "hidden_gems"]}
            existing_resp = existing_ctx.ai_response if (existing_ctx and isinstance(existing_ctx.ai_response, dict)) else {}

            if existing_resp:
                for cat in ["places", "food", "markets", "attractions", "hidden_gems"]:
                    existing_items = existing_resp.get(cat, [])
                    seed_names = {PlaceQualityValidator.normalize_place_name(p.get("name")) for p in merged_bucket[cat]}
                    for old_item in existing_items:
                        old_norm = PlaceQualityValidator.normalize_place_name(old_item.get("name"))
                        if old_norm and old_norm not in seed_names:
                            merged_bucket[cat].append(old_item)
                            seed_names.add(old_norm)

            all_places = merged_bucket["places"] + merged_bucket["food"] + merged_bucket["markets"] + merged_bucket["attractions"] + merged_bucket["hidden_gems"]
            if not all_places:
                continue

            lats = [p["lat"] for p in all_places if p.get("lat")]
            lngs = [p["lng"] for p in all_places if p.get("lng")]
            avg_lat = sum(lats) / len(lats) if lats else 28.6139
            avg_lng = sum(lngs) / len(lngs) if lngs else 77.2090

            curated_tips = CITY_TIPS.get(city_key, [
                f"Curated local recommendations for {city_title}.",
                f"Explore student hangouts and top local spots in {city_title}."
            ])

            ai_payload = {
                "location": city_title,
                "coordinates": {"lat": avg_lat, "lng": avg_lng},
                "places": merged_bucket["places"],
                "food": merged_bucket["food"],
                "markets": merged_bucket["markets"],
                "attractions": merged_bucket["attractions"],
                "hidden_gems": merged_bucket["hidden_gems"],
                "tips": curated_tips,
                "enriching": False
            }

            # Upsert into AIContext
            if not existing_ctx:
                db.add(AIContext(
                    query=city_key,
                    ai_response=ai_payload,
                    sources=["manual_seed"],
                    confidence_score=1.0,
                    search_count=1
                ))
            else:
                existing_ctx.ai_response = ai_payload
                existing_ctx.confidence_score = 1.0

            # Special aliases for Muradnagar, Ghaziabad, Modinagar & all seeded place names
            if "muradnagar" in city_key:
                aliases = ["kiet", "kiet ghaziabad", "kiet group of institutions", "kiet college", "kiet muradnagar", "muradnagar ghaziabad", "muradnagar up"]
            elif "ghaziabad" in city_key:
                aliases = ["ghaziabad up", "ghaziabad city", "rdc ghaziabad", "raj nagar ghaziabad", "indirapuram ghaziabad", "mohan nagar"]
            elif "modinagar" in city_key:
                aliases = ["modinagar up", "modinagar ghaziabad", "modi nagar"]
            else:
                aliases = []

            # Also add every seeded place's normalized name for this city
            for p_item in merged_bucket.get("attractions", []) + merged_bucket.get("food", []) + merged_bucket.get("hidden_gems", []) + merged_bucket.get("markets", []):
                p_norm = PlaceQualityValidator.normalize_place_name(p_item.get("name", ""))
                if p_norm and p_norm not in aliases:
                    aliases.append(p_norm)

            for alias in aliases:
                alias_ctx = db.query(AIContext).filter(AIContext.query == alias).first()
                # Create localized payload prioritizing this place if coordinates match
                alias_payload = dict(ai_payload)
                if not alias_ctx:
                    db.add(AIContext(
                        query=alias,
                        ai_response=alias_payload,
                        sources=["manual_seed"],
                        confidence_score=1.0
                    ))
                else:
                    alias_ctx.ai_response = alias_payload
                    alias_ctx.confidence_score = 1.0

            db.commit()
            logger.info(f"Updated AIContext for '{city_key}' with {len(all_places)} places and {len(aliases)} aliases.")

            # 5. Populate Valkey cache for instant search
            if sync_cache:
                try:
                    await cache_service.set_cache(f"search:{city_key}", ai_payload, ttl=604800)
                    for alias in aliases:
                        await cache_service.set_cache(f"search:{alias}", ai_payload, ttl=604800)
                    logger.info(f"Pre-warmed Valkey cache for query: {city_key} and {len(aliases)} aliases")
                except Exception as c_err:
                    logger.warning(f"Valkey cache warming skipped/failed: {c_err}")

    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Ghumo Database with Places JSON")
    parser.add_argument("--file", default="data/places_seed.json", help="Path to JSON seed file")
    args = parser.parse_args()

    asyncio.run(seed_places(args.file))
