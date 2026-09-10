import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_suggestions_empty_or_mocked():
    with patch("app.services.place_image_resolver.place_image_resolver.resolve_places_batch", new_callable=AsyncMock) as mock_resolve:
        async def mock_batch(places, timeout=4.0):
            for p in places:
                p["image"] = {
                    "url": "https://upload.wikimedia.org/wikipedia/commons/test.jpg",
                    "provider": "wikimedia",
                    "attribution": "Test Author"
                }

        mock_resolve.side_effect = mock_batch

        response = client.get("/suggestions?limit=5")
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "suggestions" in data
        assert isinstance(data["suggestions"], list)

        for item in data["suggestions"]:
            assert item["image"]["url"] is not None
            assert item["image"]["url"] != ""
