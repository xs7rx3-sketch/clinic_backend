import asyncio
from dataclasses import dataclass
from typing import Optional

from pymongo import AsyncMongoClient

from ..abstract.pool import BaseMongoPool, BaseMongoPoolManager
from ..defaults import (
    DB_POOL_CONNECTION_TIMEOUT,
    DB_POOL_MAX_CONS,
    DB_POOL_MIN_CONS,
    DB_POOL_RESPONSE_TIMEOUT,
    DB_POOL_SERVER_TIMEOUT,
)


@dataclass(slots=True)
class AsyncMongoPool(BaseMongoPool[AsyncMongoClient]):
    pass


class AsyncMongoPoolManager(BaseMongoPoolManager[AsyncMongoPool, AsyncMongoClient]):
    def __init__(
        self,
        *,
        min_cons: int = DB_POOL_MIN_CONS,
        max_cons: int = DB_POOL_MAX_CONS,
        srv_timeout: int = DB_POOL_SERVER_TIMEOUT,
        conn_timeout: int = DB_POOL_CONNECTION_TIMEOUT,
        resp_timeout: int = DB_POOL_RESPONSE_TIMEOUT,
    ) -> None:
        super().__init__(
            min_cons=min_cons,
            max_cons=max_cons,
            srv_timeout=srv_timeout,
            conn_timeout=conn_timeout,
            resp_timeout=resp_timeout,
        )
        self._lock = asyncio.Lock()

    def _create_client(self, uri: str) -> AsyncMongoClient:
        return AsyncMongoClient(uri, **self._client_config)

    def _build_pool(
        self,
        *,
        name: str,
        uri: str,
        database: str,
        client: AsyncMongoClient,
    ) -> AsyncMongoPool:
        return AsyncMongoPool(
            name=name,
            uri=uri,
            database=database,
            client=client,
        )

    async def register(self, *, name: str, uri: str) -> None:
        async with self._lock:
            self._register(name=name, uri=uri)

    async def close_pool(self, *, name: Optional[str] = None, uri: Optional[str] = None) -> None:
        async with self._lock:
            pool = self.get_pool(name=name, uri=uri)
            if pool is None:
                return

            await pool.client.aclose()
            self._pools.remove(pool)

    async def close_all(self) -> None:
        async with self._lock:
            await asyncio.gather(*(pool.client.aclose() for pool in self._pools))
            self._pools.clear()
