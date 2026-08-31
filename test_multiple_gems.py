import asyncio
import json
import httpx

async def test_locations():
    locations = [
        "kiet",
        "hauz khaas",
        "muradnagar",
        "modi nagar",
        "har ki pawri",
        "rajendrqa nagar bareilly"
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for loc in locations:
            print(f"\n--- Testing hidden gems for: {loc} ---")
            try:
                res = await client.get(f"http://127.0.0.1:8000/hidden-gems", params={"location": loc})
                if res.status_code == 200:
                    data = res.json()
                    print(f"Found {len(data)} gems.")
                    if data:
                        print(json.dumps(data, indent=2))
                else:
                    print(f"Error: {res.status_code} - {res.text}")
            except Exception as e:
                print(f"Request failed: {e}")

asyncio.run(test_locations())
