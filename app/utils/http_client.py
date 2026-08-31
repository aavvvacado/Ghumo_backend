import logging
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

async def safe_get_json(url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None, timeout: int = 10) -> Any:
    """Safely fetch JSON from a URL, logging errors and returning empty dict/list on failure."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e.response.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching {url}: {str(e)}")
            return {}

async def safe_post_json(url: str, data: Optional[Dict] = None, timeout: int = 15) -> Any:
    """Safely POST and fetch JSON from a URL."""
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error {e.response.status_code} from {url}: {e.response.text[:200]}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error posting to {url}: {str(e)}")
            return {}
