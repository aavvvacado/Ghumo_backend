import pytest
from app.services.place_quality_validator import place_quality_validator

def test_validate_valid_place_item():
    item = {
        "name": "Taj Mahal",
        "lat": 27.1751,
        "lng": 78.0421,
        "category": "attraction"
    }
    is_valid, reason, sanitized = place_quality_validator.validate_place_item(item)
    assert is_valid is True
    assert sanitized["name"] == "Taj Mahal"
    assert sanitized["type"] == "attraction"

def test_validate_generic_or_empty_name():
    item1 = {"name": "", "lat": 28.6, "lng": 77.2}
    is_valid1, reason1, _ = place_quality_validator.validate_place_item(item1)
    assert is_valid1 is False

    item2 = {"name": "Unknown", "lat": 28.6, "lng": 77.2}
    is_valid2, reason2, _ = place_quality_validator.validate_place_item(item2)
    assert is_valid2 is False

def test_validate_invalid_coordinates():
    item = {"name": "Test Place", "lat": 195.0, "lng": 77.2}
    is_valid, reason, _ = place_quality_validator.validate_place_item(item)
    assert is_valid is False
    assert "out of bounds" in reason

def test_validate_zero_coordinates():
    item = {"name": "Test Place", "lat": 0.0, "lng": 0.0}
    is_valid, reason, _ = place_quality_validator.validate_place_item(item)
    assert is_valid is False

def test_filter_and_validate_enrichment_response():
    data = {
        "location": "Agra",
        "places": [
            {"name": "Taj Mahal", "lat": 27.1751, "lng": 78.0421},
            {"name": "Unknown", "lat": 27.1, "lng": 78.0}
        ],
        "food": [
            {"name": "Petha Shop", "lat": 27.18, "lng": 78.02}
        ]
    }
    is_valid, reason, sanitized = place_quality_validator.filter_and_validate_enrichment_response(data)
    assert is_valid is True
    assert len(sanitized["places"]) == 1
    assert sanitized["places"][0]["name"] == "Taj Mahal"
    assert len(sanitized["food"]) == 1

def test_filter_all_invalid_returns_false():
    data = {
        "location": "Empty Void",
        "places": [{"name": "Unknown"}],
        "food": [{"name": "N/A"}]
    }
    is_valid, reason, _ = place_quality_validator.filter_and_validate_enrichment_response(data)
    assert is_valid is False
