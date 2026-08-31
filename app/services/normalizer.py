import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class NormalizerService:
    def __init__(self):
        self.noise_keywords = ["tower", "tour", "wall", "corner", "structural element"]

    def normalize_places(self, raw_data: Any, source: str) -> List[Dict[str, Any]]:
        """
        Normalize raw data from OSM or OpenTripMap into a unified format.
        Source: 'osm' or 'opentripmap'
        """
        normalized = []
        
        if source == "osm":
            elements = raw_data.get("elements", [])
            for el in elements:
                name = el.get("tags", {}).get("name")
                if not name:
                    continue
                
                # Filtering noise
                if any(kw in name.lower() for kw in self.noise_keywords):
                    continue
                
                kind = el.get("tags", {}).get("amenity") or el.get("tags", {}).get("shop") or "place"
                
                normalized.append({
                    "name": name,
                    "type": kind,
                    "lat": el.get("lat"),
                    "lng": el.get("lon"),
                    "distance": 0, # OSM around doesn't give distance directly
                    "source": "osm",
                    "external_id": f"osm_{el.get('id')}"
                })
        
        elif source == "opentripmap":
            if not isinstance(raw_data, list):
                logger.warning(f"Expected list for OTM data, got {type(raw_data)}")
                return []
            
            for p in raw_data:
                name = p.get("name")
                if not name:
                    continue
                
                # Filtering noise
                if any(kw in name.lower() for kw in self.noise_keywords):
                    continue
                
                kinds = p.get("kinds", "").split(",")
                kind = kinds[0] if kinds else "attraction"
                
                normalized.append({
                    "name": name,
                    "type": kind,
                    "lat": p.get("point", {}).get("lat"),
                    "lng": p.get("point", {}).get("lon"),
                    "distance": p.get("dist", 0),
                    "source": "opentripmap",
                    "external_id": p.get("xid")
                })
        
        logger.info(f"Normalized {len(normalized)} places from {source}")
        return normalized

normalizer = NormalizerService()
