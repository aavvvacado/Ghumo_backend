import pytest
from httpx import AsyncClient
from app.main import app

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Ghumo Backend API"}

@pytest.mark.asyncio
async def test_search_no_query():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.get("/search")
    assert response.status_code == 422  # Validation error (missing query)

@pytest.mark.asyncio
async def test_itinerary_post_validation():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/itinerary", json={})
    assert response.status_code == 422  # Validation error (missing required fields)
