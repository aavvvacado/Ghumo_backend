import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as c:
        for q in ['KIET Deemed to be University', 'KIET']:
            r = await c.get('https://nominatim.openstreetmap.org/search', params={'q': q, 'format': 'json', 'limit': 1}, headers={'User-Agent': 'Bot/1.0'})
            data = r.json()
            if data:
                print(f"Found {q}: {data[0]['lat']}, {data[0]['lon']}")
            else:
                print(f"Not found: {q}")

asyncio.run(test())
