import asyncio
import json
from app.services.search_service import search_service
from app.services.cache_service import cache_service

async def test():
    if cache_service.valkey_client:
        await cache_service.valkey_client.flushdb()
    
    print('Testing KIET Deemed to be University...')
    res = await search_service.search_all('KIET Deemed to be University Ghaziabad')
    print(json.dumps(res, indent=2))
    print('\n===============================\n')
    print('Testing Ghaziabad...')
    res2 = await search_service.search_all('Ghaziabad')
    print(json.dumps(res2, indent=2))

asyncio.run(test())
