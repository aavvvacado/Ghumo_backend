import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.place_image_resolver import (
    PlaceImageResolver, WikimediaProvider, UnsplashProvider, GooglePlacesProvider, slugify
)

def test_slugify_and_cache_key():
    resolver = PlaceImageResolver()
    key1 = resolver.get_cache_key("Taj Mahal", "Agra", "India")
    key2 = resolver.get_cache_key("Taj Mahal", "Delhi", "India")
    assert key1 != key2
    assert "taj_mahal" in key1
    assert "agra" in key1

def test_wikimedia_provider_success():
    async def _test():
        with patch("httpx.AsyncClient.get") as mock_get:
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {
                "query": {
                    "pages": {
                        "123": {
                            "imageinfo": [{
                                "url": "https://upload.wikimedia.org/wikipedia/commons/1/1e/Taj_Mahal.jpg",
                                "user": "TestUser",
                                "extmetadata": {
                                    "Artist": {"value": "Test Artist"},
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"}
                                }
                            }]
                        }
                    }
                }
            }
            mock_get.return_value = mock_res

            img_data = await WikimediaProvider.resolve_image("Taj Mahal", "Agra")
            assert img_data is not None
            assert img_data["source"] == "wikimedia"
            assert "upload.wikimedia.org" in img_data["url"]
            assert "CC BY-SA 4.0" in img_data["attribution"]
    asyncio.run(_test())

def test_unsplash_fallback_when_wikimedia_fails():
    async def _test():
        resolver = PlaceImageResolver()
        with patch.object(WikimediaProvider, "resolve_image", new_callable=AsyncMock) as mock_wiki, \
             patch.object(UnsplashProvider, "resolve_image", new_callable=AsyncMock) as mock_unsplash, \
             patch("app.services.cache_service.cache_service.get_cache", new_callable=AsyncMock, return_value=None), \
             patch("app.services.cache_service.cache_service.set_cache", new_callable=AsyncMock):

            mock_wiki.return_value = None
            mock_unsplash.return_value = {
                "url": "https://images.unsplash.com/photo-12345",
                "source": "unsplash",
                "attribution": "Photo by Jane Doe on Unsplash"
            }

            result = await resolver.resolve_place_image("Random Place", "Jaipur")
            assert result is not None
            assert result["source"] == "unsplash"
            assert "unsplash.com" in result["url"]
    asyncio.run(_test())

def test_no_provider_returns_image():
    async def _test():
        resolver = PlaceImageResolver()
        with patch.object(WikimediaProvider, "resolve_image", new_callable=AsyncMock, return_value=None), \
             patch.object(UnsplashProvider, "resolve_image", new_callable=AsyncMock, return_value=None), \
             patch.object(GooglePlacesProvider, "resolve_image", new_callable=AsyncMock, return_value=None), \
             patch("app.services.cache_service.cache_service.get_cache", new_callable=AsyncMock, return_value=None), \
             patch("app.services.cache_service.cache_service.set_cache", new_callable=AsyncMock):

            result = await resolver.resolve_place_image("Nonexistent Fake Place XYZ", "Nowhere")
            assert result is None
    asyncio.run(_test())

def test_batch_resolution_handles_multiple_places_concurrently():
    async def _test():
        resolver = PlaceImageResolver()
        places = [
            {"name": "Amber Fort", "city": "Jaipur"},
            {"name": "Hawa Mahal", "city": "Jaipur"},
            {"name": "City Palace", "city": "Jaipur"}
        ]

        with patch.object(resolver, "resolve_place_image", new_callable=AsyncMock) as mock_resolve:
            mock_resolve.side_effect = [
                {"url": "https://img1.com", "source": "wikimedia", "attribution": "Attr 1"},
                {"url": "https://img2.com", "source": "unsplash", "attribution": "Attr 2"},
                None
            ]

            resolved_places = await resolver.resolve_places_batch(places, city="Jaipur")
            assert len(resolved_places) == 3
            assert resolved_places[0]["image"]["url"] == "https://img1.com"
            assert resolved_places[1]["image"]["url"] == "https://img2.com"
            assert resolved_places[2]["image"] is None
    asyncio.run(_test())

def test_cache_hit_prevents_external_api_calls():
    async def _test():
        resolver = PlaceImageResolver()
        cached_payload = {
            "image": {
                "url": "https://cached-image.com/pic.jpg",
                "source": "wikimedia",
                "attribution": "Cached Attr"
            }
        }

        with patch("app.services.cache_service.cache_service.get_cache", new_callable=AsyncMock, return_value=cached_payload), \
             patch.object(WikimediaProvider, "resolve_image", new_callable=AsyncMock) as mock_wiki:

            result = await resolver.resolve_place_image("Red Fort", "Delhi")
            assert result["url"] == "https://cached-image.com/pic.jpg"
            mock_wiki.assert_not_called()
    asyncio.run(_test())
