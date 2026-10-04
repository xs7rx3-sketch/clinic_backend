import asyncio
from typing import Any, TypeAlias, cast

from pymongo.asynchronous.cursor import AsyncCursor
from pymongo.results import (
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)

from ..abstract.db import BaseMongoDB
from .pool import AsyncMongoPool, AsyncMongoPoolManager

MongoDoc: TypeAlias = dict[str, Any]


class AsyncMongoDB(BaseMongoDB[AsyncMongoPoolManager, AsyncMongoPool]):
    async def list_databases(self) -> dict[str, list[str]]:
        self._validate_connections()

        databases: dict[str, list[str]] = {}
        for pool in self.pool.pools:
            dbs_cursor = await pool.client.list_databases()
            databases[pool.name] = [database["name"] async for database in dbs_cursor]

        return databases

    async def list_collections(self) -> dict[str, list[str]]:
        self._validate_connections()

        collections: dict[str, list[str]] = {}
        for pool in self.pool.pools:
            database = pool.client[pool.database]
            cols_cursor = await database.list_collections()
            collections[pool.name] = [collection["name"] async for collection in cols_cursor]

        return collections

    async def find(self, document: MongoDoc, **kwargs) -> AsyncCursor:
        self._validate_collection()
        self._validate_connections()

        pool = self.pool.pools[0]
        collection = cast(str, self.collection)
        return pool.client[pool.database][collection].find(document, **kwargs)

    async def find_one(self, document: MongoDoc, **kwargs) -> MongoDoc:
        self._validate_collection()
        self._validate_connections()

        pool = self.pool.pools[0]
        collection = cast(str, self.collection)
        return await pool.client[pool.database][collection].find_one(document, **kwargs)  # type: ignore

    async def insert_one(self, document: MongoDoc, **kwargs) -> InsertOneResult:
        self._validate_collection()
        self._validate_connections()

        prepared = self._prepare_insert_one_document(document)

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].insert_one(prepared.copy(), **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(InsertOneResult, result[0])

    async def insert_many(self, documents: list[MongoDoc], **kwargs) -> InsertManyResult:
        self._validate_collection()
        self._validate_connections()

        prepared = self._prepare_insert_many_documents(documents)

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].insert_many(prepared, **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(InsertManyResult, result[0])

    async def update_one(self, _filter: dict[str, Any], update: dict[str, Any], **kwargs) -> UpdateResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].update_one(_filter, update, **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(UpdateResult, result[0])

    async def update_many(self, _filter: dict[str, Any], update: dict[str, Any], **kwargs) -> UpdateResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].update_many(_filter, update, **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(UpdateResult, result[0])

    async def delete_one(self, _filter: dict[str, Any], **kwargs) -> DeleteResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].delete_one(_filter, **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(DeleteResult, result[0])

    async def delete_many(self, _filter: dict[str, Any], **kwargs) -> DeleteResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        tasks = [pool.client[pool.database][collection].delete_many(_filter, **kwargs) for pool in self.pool.pools]
        result = await asyncio.gather(*tasks, return_exceptions=True)
        self._catch_mongo_exception(result, pools=self.pool.pools)

        return cast(DeleteResult, result[0])
