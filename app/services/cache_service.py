import json
import logging
from typing import Optional, Any
import valkey.asyncio as valkey
from app.utils.config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.valkey_client: Optional[valkey.Valkey] = None

    async def connect(self):
        if not self.valkey_client:
            try:
                self.valkey_client = valkey.from_url(settings.VALKEY_URL, decode_responses=True)
                await self.valkey_client.ping()
                logger.info("Connected to Valkey successfully.")
            except Exception as e:
                logger.error(f"Failed to connect to Valkey: {e}")
                self.valkey_client = None

    async def get_cache(self, key: str) -> Optional[Any]:
        if not self.valkey_client:
            await self.connect()
        
        if not self.valkey_client:
            return None

        try:
            value = await self.valkey_client.get(key)
            if value:
                logger.info(f"Cache hit for key: {key}")
                return json.loads(value)
            logger.info(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache for {key}: {e}")
            return None

    async def set_cache(self, key: str, value: Any, ttl: int = 3600):
        if not self.valkey_client:
            await self.connect()

        if not self.valkey_client:
            return

        try:
            await self.valkey_client.set(key, json.dumps(value), ex=ttl)
            logger.info(f"Set cache for key: {key} (TTL: {ttl}s)")
        except Exception as e:
            logger.error(f"Error setting cache for {key}: {e}")
            # If we lose connection, try to reconnect next time
            if "Closed" in str(e) or "Connection" in str(e):
                self.valkey_client = None

    async def delete_cache(self, key: str):
        if not self.valkey_client:
            await self.connect()

        if not self.valkey_client:
            return

        try:
            await self.valkey_client.delete(key)
            logger.info(f"Deleted cache key: {key}")
        except Exception as e:
            logger.error(f"Error deleting cache for {key}: {e}")
            if "Closed" in str(e) or "Connection" in str(e):
                self.valkey_client = None

cache_service = CacheService()
