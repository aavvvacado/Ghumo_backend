import logging
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)

GENERIC_NAMES = {"unknown", "point of interest", "place", "n/a", "null", "undefined", "checking...", "none", "location"}

class PlaceQualityValidator:
    """
    Dedicated quality validation layer to ensure invalid, corrupt, or zero-information
    place items are discarded BEFORE expensive downstream enrichment and BEFORE persistence.
    """

    @classmethod
    def validate_place_item(cls, item: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates a single place/attraction/food/market dictionary.
        Returns (is_valid, failure_reason, sanitized_item).
        """
        if not isinstance(item, dict):
            return False, "Item is not a dictionary", {}

        name = str(item.get("name") or item.get("place") or "").strip()
        if not name or len(name) < 2:
            return False, "Place name is empty or too short", {}

        if name.lower() in GENERIC_NAMES:
            return False, f"Place name '{name}' is generic/placeholder", {}

        # Validate coordinates if provided
        lat = item.get("lat")
        lng = item.get("lng")
        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
                    return False, f"Coordinates out of bounds: ({lat_f}, {lng_f})", {}
                if lat_f == 0.0 and lng_f == 0.0:
                    return False, "Coordinates (0.0, 0.0) are invalid for real places", {}
            except (ValueError, TypeError):
                return False, f"Invalid coordinate format: lat={lat}, lng={lng}", {}

        # Ensure sanitized item preserves essential structure
        sanitized = dict(item)
        sanitized["name"] = name
        if "type" not in sanitized and "category" in sanitized:
            sanitized["type"] = sanitized["category"]

        return True, "Valid place item", sanitized

    @classmethod
    def filter_and_validate_enrichment_response(cls, data: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates an entire travel enrichment response dictionary.
        Filters out invalid items from places, food, markets, attractions, hidden_gems.
        Returns (is_valid, reason, sanitized_data).
        """
        if not isinstance(data, dict):
            return False, "Enrichment data is not a dictionary", {}

        location = str(data.get("location") or "").strip()
        if not location:
            return False, "Location header is missing or empty", {}

        sanitized = dict(data)
        categories = ["places", "food", "markets", "attractions", "hidden_gems"]
        valid_items_total = 0

        for cat in categories:
            raw_list = sanitized.get(cat, [])
            if not isinstance(raw_list, list):
                sanitized[cat] = []
                continue

            valid_list = []
            for raw_item in raw_list:
                is_valid, reason, clean_item = cls.validate_place_item(raw_item)
                if is_valid:
                    valid_list.append(clean_item)
                    valid_items_total += 1
                else:
                    logger.debug(f"Discarding invalid item in '{cat}': {reason}")

            sanitized[cat] = valid_list

        if valid_items_total == 0:
            return False, f"No valid place items found for '{location}'", sanitized

        return True, f"Found {valid_items_total} valid items", sanitized

place_quality_validator = PlaceQualityValidator()
