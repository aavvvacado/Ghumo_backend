import pytest
import json
from unittest.mock import patch, AsyncMock
from app.services.itinerary_service import itinerary_service
from app.api.schemas import ItineraryRequest, ItineraryResponse

@pytest.mark.asyncio
async def test_parse_user_intent_structured_fallback():
    """Test intent parsing when structured location and duration are given directly without prompt."""
    intent = await itinerary_service.parse_user_intent(
        prompt=None,
        location="Jaipur",
        time_available="3 days",
        interests=["heritage", "palaces"],
        budget="5000 INR"
    )
    assert intent["destination"] == "Jaipur"
    assert intent["duration"] == "3 days"
    assert intent["mode"] == "day_wise"
    assert intent["budget"] == "5000 INR"
    assert "heritage" in intent["interests"]

@pytest.mark.asyncio
async def test_parse_user_intent_short_trip_fallback():
    """Test intent parsing automatically identifies time_wise mode for hour-based or short trips."""
    intent = await itinerary_service.parse_user_intent(
        prompt=None,
        location="Chandni Chowk",
        time_available="4 hours afternoon",
        interests=["street food"],
        budget="1000 INR"
    )
    assert intent["destination"] == "Chandni Chowk"
    assert intent["mode"] == "time_wise"

@pytest.mark.asyncio
async def test_parse_user_intent_freeform_prompt():
    """Test NLP intent extraction from conversational user text."""
    mock_ai_response = json.dumps({
        "destination": "Goa",
        "duration": "3 days",
        "mode": "day_wise",
        "budget": "10000 INR",
        "interests": ["beaches", "seafood", "nightlife"],
        "stay_preference": "Anjuna or Baga beach resort"
    })
    
    with patch("app.services.ai_service.ai_service.generate_content", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_ai_response
        intent = await itinerary_service.parse_user_intent(
            prompt="iam visiting goa for 3 days with 10000 budget"
        )
        assert intent["destination"] == "Goa"
        assert intent["duration"] == "3 days"
        assert intent["mode"] == "day_wise"
        assert intent["budget"] == "10000 INR"
        assert "beaches" in intent["interests"]

@pytest.mark.asyncio
async def test_generate_markdown_table():
    """Verify markdown table format contains clean headers, alignments, and chunk dividers."""
    day_wise_plan = {
        "mode": "day_wise",
        "days": [
            {
                "day": 1,
                "title": "Historical & Heritage Exploration",
                "stay_recommendation": "Heritage Haveli in Old City",
                "activities": [
                    {
                        "time_slot": "09:00 AM - 11:30 AM",
                        "place": "Hawa Mahal",
                        "duration": "2.5 hours",
                        "purpose": "Sightseeing & Architecture",
                        "cost_estimate": "₹100"
                    }
                ]
            }
        ]
    }
    table = itinerary_service._generate_markdown_table(day_wise_plan)
    assert "| Timing / Slot | Place / Landmark | Duration | Purpose & Highlights | Estimated Cost |" in table
    assert "| 09:00 AM - 11:30 AM | **Hawa Mahal** | 2.5 hours | Sightseeing & Architecture | ₹100 |" in table

@pytest.mark.asyncio
async def test_generate_itinerary_full_flow():
    """Verify full end-to-end itinerary generation with simulated search and AI responses."""
    mock_ai_itinerary = json.dumps({
        "destination": "Varanasi",
        "duration": "2 days",
        "mode": "day_wise",
        "stay_area": "Ghats / Assi Ghat",
        "summary": "Immerse yourself in timeless spiritual rituals and riverfront heritage.",
        "budget_breakdown": {
            "stay": "₹2,500",
            "food": "₹1,200",
            "activities": "₹800",
            "transport": "₹500"
        },
        "days": [
            {
                "day": 1,
                "title": "Sacred Ghats and Evening Aarti",
                "stay_recommendation": "River-facing Guesthouse near Dashashwamedh",
                "estimated_day_cost": "₹2,000",
                "activities": [
                    {
                        "time_slot": "06:00 AM - 08:00 AM",
                        "place": "Dashashwamedh Ghat",
                        "duration": "2 hours",
                        "purpose": "Morning Boat Ride and Sunrise Photography",
                        "cost_estimate": "₹300"
                    }
                ]
            }
        ]
    })

    async def mock_batch_resolve(places, city="", timeout=4.0):
        for p in places:
            p["image"] = {"url": "https://images.unsplash.com/photo-varanasi.jpg", "source": "unsplash"}

    with patch("app.services.search_service.search_service.search_all", new_callable=AsyncMock) as mock_search, \
         patch("app.services.ai_service.ai_service.generate_content", new_callable=AsyncMock) as mock_gen, \
         patch("app.services.place_image_resolver.place_image_resolver.resolve_places_batch", side_effect=mock_batch_resolve):
        
        mock_search.return_value = {
            "attractions": [{"name": "Dashashwamedh Ghat"}],
            "restaurants": [{"name": "Kashi Tea Stall"}],
            "markets": [{"name": "Vishwanath Gali"}]
        }
        mock_gen.return_value = mock_ai_itinerary

        result = await itinerary_service.generate_itinerary(
            location="Varanasi",
            time_available="2 days",
            interests=["spirituality", "culture"],
            budget="5000 INR"
        )

        assert result["location"] == "Varanasi"
        assert "plan" in result
        assert result["plan"]["mode"] == "day_wise"
        assert len(result["plan"]["days"]) == 1
        assert result["plan"]["days"][0]["activities"][0]["place"] == "Dashashwamedh Ghat"
        assert result["plan"]["days"][0]["activities"][0]["image"]["url"] == "https://images.unsplash.com/photo-varanasi.jpg"
        assert "| Timing / Slot | Place / Landmark |" in result["plan"]["markdown_table"]
        assert "budget_breakdown" in result["plan"]
        assert result["plan"]["budget_breakdown"]["stay"] == "₹2,500"
        assert "recommended_places" in result
        assert "recommended_attractions" in result
