import logging
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from app.database.models import Place, PlaceRelation
from app.database.session import SessionLocal
import math

logger = logging.getLogger(__name__)

class KnowledgeGraphService:
    def detect_and_store_relations(self, places: List[Dict[str, Any]], city: str, corpora: dict = None):
        """Analyze a list of places and establish relationships."""
        db = SessionLocal()
        try:
            # 1. Fetch persistent IDs for these places from DB
            db_places = db.query(Place).filter(Place.city == city).all()
            place_map = {p.external_id: p for p in db_places}

            for p1_data in places:
                p1_ext_id = p1_data.get("external_id")
                p1 = place_map.get(p1_ext_id) if p1_ext_id else None
                if not p1:
                    continue

                for p2_data in places:
                    p2_ext_id = p2_data.get("external_id")
                    if p1_ext_id and p1_ext_id == p2_ext_id:
                        continue
                    
                    p2 = place_map.get(p2_ext_id) if p2_ext_id else None
                    if not p2:
                        continue

                    # Relation Logic
                    dist = self._calculate_distance(p1.lat, p1.lng, p2.lat, p2.lng)
                    
                    # Nearby Relation (< 500m)
                    if dist < 0.5:
                        self._add_relation(db, p1.id, p2.id, "nearby", 1.0 - (dist/0.5))
                    
                    # Same Cluster / Contextual (e.g., Restaurant near Landmark)
                    if p1.category in ["restaurant", "cafe", "food"] and p2.category in ["attraction", "hidden_gem"] and dist < 0.5:
                        self._add_relation(db, p1.id, p2.id, "food_near_landmark", 0.9)
                        
                    if p1.category in ["market"] and p2.category in ["attraction", "hidden_gem"] and dist < 0.8:
                        self._add_relation(db, p1.id, p2.id, "market_near_landmark", 0.8)

            # 2. Detect Media Mentions if corpora provided
            if corpora:
                yt_text = corpora.get("youtube", "").lower()
                reddit_text = corpora.get("reddit", "").lower()
                blog_text = corpora.get("blog", "").lower()
                
                for p1_data in places:
                    p1_ext_id = p1_data.get("external_id")
                    p1 = place_map.get(p1_ext_id) if p1_ext_id else db.query(Place).filter(Place.name == p1_data.get("name"), Place.city == city).first()
                    if not p1: continue
                    
                    p_name = p1.name.lower()
                    
                    if yt_text and p_name in yt_text:
                        self._add_relation(db, p1.id, None, "video_mention", 0.85)
                    if reddit_text and p_name in reddit_text:
                        self._add_relation(db, p1.id, None, "reddit_mention", 0.80)
                    if blog_text and p_name in blog_text:
                        self._add_relation(db, p1.id, None, "blog_mention", 0.75)
            
            db.commit()
            logger.info(f"Knowledge graph relationships updated for {city}")
        except Exception as e:
            logger.error(f"Failed to create graph relations: {e}")
            db.rollback()
        finally:
            db.close()

    def get_related_places(self, place_id: int) -> List[Dict[str, Any]]:
        db = SessionLocal()
        try:
            relations = db.query(PlaceRelation).filter(PlaceRelation.place_id == place_id).all()
            result = []
            for rel in relations:
                related = rel.related_place
                result.append({
                    "name": related.name,
                    "relation": rel.relation_type,
                    "confidence": rel.confidence
                })
            return result
        finally:
            db.close()

    def _add_relation(self, db: Session, p1_id: int, p2_id: int, rel_type: str, confidence: float):
        if p2_id is not None:
            existing = db.query(PlaceRelation).filter(
                PlaceRelation.place_id == p1_id,
                PlaceRelation.related_place_id == p2_id,
                PlaceRelation.relation_type == rel_type
            ).first()
        else:
            existing = db.query(PlaceRelation).filter(
                PlaceRelation.place_id == p1_id,
                PlaceRelation.related_place_id == None,
                PlaceRelation.relation_type == rel_type
            ).first()
            
        if not existing:
            new_rel = PlaceRelation(
                place_id=p1_id,
                related_place_id=p2_id,
                relation_type=rel_type,
                confidence=confidence
            )
            db.add(new_rel)

    def _calculate_distance(self, lat1, lon1, lat2, lon2):
        """Haversine distance in km."""
        R = 6371
        d_lat = math.radians(lat2 - lat1)
        d_lon = math.radians(lon2 - lon1)
        a = math.sin(d_lat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c

knowledge_graph_service = KnowledgeGraphService()
