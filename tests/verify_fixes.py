import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.context_reasoning_service import context_reasoning_service
from app.services.cloudflare_service import cloudflare_service

async def test_reasoning():
    print("Testing Context Reasoning Service...")
    location = "CITM Lake, Faridabad"
    osm_data = [{"name": "CITM Lake", "category": "lake", "lat": 28.4595, "lng": 77.2800}]
    reddit_text = "CITM Lake is a hidden gem in Faridabad. It's a beautiful lake formed in an abandoned quarry."
    blog_text = "Visit CITM Lake for a peaceful getaway. It's near the Surajkund area."
    
    try:
        result = await context_reasoning_service.synthesize_travel_data(
            location=location,
            osm_data=osm_data,
            reddit_text=reddit_text,
            blog_text=blog_text
        )
        print("Reasoning Result SUCCESS:")
        import json
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"Reasoning Result FAILED: {e}")

async def test_cloudflare():
    print("\nTesting Cloudflare Service...")
    url = "https://www.google.com"
    try:
        # Just try to get content of a simple page
        content = await cloudflare_service.get_page_content(url)
        if content:
            print(f"Cloudflare SUCCESS: Got {len(content)} bytes of content.")
        else:
            print("Cloudflare FAILED: No content returned.")
    except Exception as e:
        print(f"Cloudflare EXCEPTION: {e}")

if __name__ == "__main__":
    asyncio.run(test_reasoning())
    asyncio.run(test_cloudflare())
