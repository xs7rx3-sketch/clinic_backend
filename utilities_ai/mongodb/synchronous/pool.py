from dataclasses import dataclass
from typing import Optional

from pymongo import MongoClient

from ..abstract.pool import BaseMongoPool, BaseMongoPoolManager


@dataclass(slots=True)
class MongoPool(BaseMongoPool[MongoClient]):
    pass


class MongoPoolManager(BaseMongoPoolManager[MongoPool, MongoClient]):
    def _create_client(self, uri: str) -> MongoClient:
        return MongoClient(uri, **self._client_config)

    def _build_pool(
        self,
        *,
        name: str,
        uri: str,
        database: str,
        client: MongoClient,
    ) -> MongoPool:
        return MongoPool(
            name=name,
            uri=uri,
            database=database,
            client=client,
        )

    def register(self, *, name: str, uri: str) -> None:
        self._register(name=name, uri=uri)

    def close_pool(self, *, name: Optional[str] = None, uri: Optional[str] = None) -> None:
        pool = self.get_pool(name=name, uri=uri)
        if pool is None:
            return

        pool.client.close()
        self._pools.remove(pool)

    def close_all(self) -> None:
        for pool in self._pools:
            pool.client.close()
        self._pools.clear()
