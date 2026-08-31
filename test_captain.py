import asyncio
import httpx
import json

async def test_captain_contribution():
    # 0. Admin cleanup (clear out cache & ai_context so engine is forced to build fresh)
    from app.services.cache_service import cache_service
    from app.database.session import SessionLocal
    from app.database.models import AIContext
    if cache_service.valkey_client:
        await cache_service.valkey_client.flushdb()
    db = SessionLocal()
    db.query(AIContext).filter(AIContext.query == "kiet ghaziabad").delete()
    db.commit()
    db.close()

    # 1. First, submit a contribution for KiET
    contribution = {
        "location": "kiet ghaziabad",
        "name": "Students Favorite Maggi Point TEST",
        "description": "The best midnight maggi spot just outside the campus gate. Ask for the double masala cheese loaded version.",
        "category": "hidden_gem",
        "lat": 28.7525,
        "lng": 77.4991,
        "submitted_by": "CaptainAsh"
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Submitting Contribution...")
        res = await client.post("http://127.0.0.1:8000/contribute", json=contribution)
        print(f"Status: {res.status_code}")
        print(res.json())

        # 2. Check the hidden-gems endpoint directly
        print("\n--- Verifying Hidden Gems Endpoint for kiet ghaziabad ---")
        hidden_res = await client.get("http://127.0.0.1:8000/hidden-gems", params={"location": "kiet ghaziabad"})
        print(f"Status: {hidden_res.status_code}")
        print(json.dumps(hidden_res.json(), indent=2))

asyncio.run(test_captain_contribution())
