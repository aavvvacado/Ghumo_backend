import logging
from typing import Dict, Any

from app.database.session import SessionLocal
from app.database.models import Place, HiddenGem, PlaceRelation, TravelTip, AIContext

logger = logging.getLogger(__name__)

class KnowledgeUpdater:
    def calculate_confidence_score(self, item: Dict[str, Any], corpora: dict) -> float:
        """
        Calculates a multi-signal confidence score for a place.
        score = osm_presence + reddit_mentions + blog_mentions + video_mentions
        """
        score = 0.1 # Base score for being mentioned by AI
        name = item.get("name", "").lower()
        
        if not name: return 0.0

        # 1. OSM Presence (Strong Signal for physical existence)
        source = item.get("source", "")
        if "osm" in source:
            score += 0.4
        
        if corpora:
            # 2. Reddit Mentions (Social Proof)
            if "reddit" in corpora and name in corpora["reddit"].lower():
                score += 0.2
                
            # 3. Blog Mentions (Curation Proof)
            if "blog" in corpora and name in corpora["blog"].lower():
                score += 0.2
                
            # 4. Video/YouTube Mentions (Visual Proof)
            if "youtube" in corpora and name in corpora["youtube"].lower():
                score += 0.2
            
        return min(score, 1.0)

    async def sync_intelligence_to_db(self, query_key: str, intelligence: Dict[str, Any], corpora: dict = None):
        """
        Implements self-updating database logic with Smart Merge.
        Only updates records if the new confidence score is higher.
        """
        db = SessionLocal()
        try:
            # 1. Update AI Context (High-level synthesis)
            existing_ctx = db.query(AIContext).filter(AIContext.query == query_key).first()
            if not existing_ctx:
                db.add(AIContext(
                    query=query_key,
                    ai_response=intelligence,
                    sources=list(corpora.keys()) if corpora else ["osm"],
                    confidence_score=0.9
                ))
            else:
                # Merge logic for AI Context: typically overwrite with newest synthesis
                existing_ctx.ai_response = intelligence
                if corpora:
                    existing_ctx.sources = list(set(existing_ctx.sources + list(corpora.keys())))

            # 2. Store & Merge Places (Granular Intelligence)
            from app.services.place_quality_validator import place_quality_validator
            from app.services.search_service import search_service

            for cat in ["places", "food", "markets", "attractions"]:
                for item in intelligence.get(cat, []):
                    is_valid, reason, clean_item = place_quality_validator.validate_place_item(item)
                    if not is_valid:
                        logger.debug(f"Skipping DB insert for invalid place item '{item}': {reason}")
                        continue

                    place_name = clean_item.get("name")
                    norm_name = place_name.lower().strip()
                    new_score = self.calculate_confidence_score(clean_item, corpora)
                    
                    # Search by normalized_name and city
                    existing_place = db.query(Place).filter(
                        (Place.normalized_name == norm_name) | (Place.name.ilike(place_name))
                    ).filter(Place.city.ilike(f"%{query_key}%")).first()

                    if not existing_place:
                        db.add(Place(
                            name=place_name,
                            normalized_name=norm_name,
                            category=cat,
                            lat=clean_item.get("lat"),
                            lng=clean_item.get("lng"),
                            city=query_key,
                            source=clean_item.get("source", "intelligence_engine"),
                            confidence_score=new_score,
                            source_count=1,
                            search_count=1
                        ))
                    else:
                        existing_place.search_count += 1
                        if new_score > existing_place.confidence_score:
                            logger.info(f"Upgrading data for {place_name}: {existing_place.confidence_score} -> {new_score}")
                            existing_place.confidence_score = new_score
                            existing_place.source_count += 1
                            if not existing_place.lat and clean_item.get("lat"):
                                existing_place.lat = clean_item.get("lat")
                                existing_place.lng = clean_item.get("lng")

            # 3. Store & Merge Hidden Gems
            for item in intelligence.get("hidden_gems", []):
                is_valid, reason, clean_item = place_quality_validator.validate_place_item(item)
                if not is_valid:
                    continue

                place_name = clean_item.get("name")
                new_score = self.calculate_confidence_score(clean_item, corpora)
                existing_gem = db.query(HiddenGem).filter(HiddenGem.name.ilike(place_name)).first()
                if existing_gem:
                    if new_score > existing_gem.confidence_score:
                        existing_gem.confidence_score = new_score
                else:
                    db.add(HiddenGem(
                        name=place_name,
                        category="hidden_gem",
                        lat=clean_item.get("lat"),
                        lng=clean_item.get("lng"),
                        city=query_key,
                        source=clean_item.get("source", "intelligence_engine"),
                        confidence_score=max(new_score, 0.7)
                    ))

            # 4. Store Tips (Concatenated)
            for tip_data in intelligence.get("tips", []):
                tip_text = tip_data.get("text") if isinstance(tip_data, dict) else tip_data
                if not tip_text: continue
                # Check for duplicate tips
                exists = db.query(TravelTip).filter(TravelTip.city == query_key, TravelTip.tip_text == tip_text).first()
                if not exists:
                    db.add(TravelTip(
                        city=query_key,
                        tip_text=tip_text,
                        source="intelligence_engine",
                        confidence_score=0.9
                    ))

            db.commit()
            
            # 5. Build Knowledge Graph Relations
            from app.services.knowledge_graph_service import knowledge_graph_service
            all_places = []
            for cat in ["places", "food", "markets", "attractions", "hidden_gems"]:
                all_places.extend(intelligence.get(cat, []))
            
            knowledge_graph_service.detect_and_store_relations(all_places, query_key, corpora)
            
            logger.info(f"Knowledge Smart-Merge complete for {query_key}.")
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to sync knowledge to DB for {query_key}: {e}")
        finally:
            db.close()

knowledge_updater = KnowledgeUpdater()
