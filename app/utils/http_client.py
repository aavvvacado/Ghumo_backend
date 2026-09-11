import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "GhumoTravelBot/1.0 (https://ghumo.app; travel-intelligence)",
    "Accept": "application/json, text/plain, */*"
}

async def safe_get_json(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, timeout: int = 10) -> Any:
    """Safely fetch JSON from a URL, logging errors and returning empty dict/list on failure."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url, params=params, headers=req_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e.response.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {str(e)}")
            return {}

async def safe_post_json(url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None, timeout: int = 15) -> Any:
    """Safely POST and fetch JSON from a URL."""
    req_headers = dict(DEFAULT_HEADERS)
    if headers:
        req_headers.update(headers)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, data=data, headers=req_headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e.response.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error posting to {url}: {str(e)}")
            return {}
