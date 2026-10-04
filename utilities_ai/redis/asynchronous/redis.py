import asyncio
import pickle
from typing import Any, Optional

import redis.asyncio as redis

from ..abstract.redis import BaseStateManager
from ..defaults import REDIS_DATABASE


# TODO: Add useful logs that can be disabled.
class AsyncStateManager(BaseStateManager):
    def __init__(self, db: int = REDIS_DATABASE, *, host: Optional[str] = None, port: Optional[int] = None):
        super().__init__(db, host=host, port=port)

        self.redis = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=False)

    async def store_state(self, key: str, value: Any):
        serialized = await asyncio.to_thread(pickle.dumps, value)
        await self.redis.set(key, serialized)

    async def fetch_state(self, key: str) -> Optional[Any]:
        serialized = await self.redis.get(key)
        return await asyncio.to_thread(pickle.loads, serialized) if serialized else None

    async def reset_state(self, key: Optional[str] = None, all_states: bool = False):
        if not all_states and key is None:
            return

        if all_states:
            await self.redis.flushdb()
            return

        await self.redis.delete(key)  # type: ignore

    async def close(self):
        await self.redis.aclose()
