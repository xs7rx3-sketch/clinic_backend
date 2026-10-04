from typing import Any, TypeAlias, cast

from pymongo.results import (
    DeleteResult,
    InsertManyResult,
    InsertOneResult,
    UpdateResult,
)
from pymongo.synchronous.cursor import Cursor

from ..abstract.db import BaseMongoDB
from .pool import MongoPool, MongoPoolManager

MongoDoc: TypeAlias = dict[str, Any]


class MongoDB(BaseMongoDB[MongoPoolManager, MongoPool]):
    def list_databases(self) -> dict[str, list[str]]:
        self._validate_connections()

        databases: dict[str, list[str]] = {}
        for pool in self.pool.pools:
            databases[pool.name] = [database["name"] for database in pool.client.list_databases()]

        return databases

    def list_collections(self) -> dict[str, list[str]]:
        self._validate_connections()

        collections: dict[str, list[str]] = {}
        for pool in self.pool.pools:
            database = pool.client[pool.database]
            collections[pool.name] = [collection["name"] for collection in database.list_collections()]

        return collections

    def find(self, document: MongoDoc, **kwargs) -> Cursor:
        self._validate_collection()
        self._validate_connections()

        pool = self.pool.pools[0]
        collection = cast(str, self.collection)
        return pool.client[pool.database][collection].find(document, **kwargs)

    def find_one(self, document: MongoDoc, **kwargs) -> MongoDoc:
        self._validate_collection()
        self._validate_connections()

        pool = self.pool.pools[0]
        collection = cast(str, self.collection)
        doc = pool.client[pool.database][collection].find_one(document, **kwargs)
        return cast(MongoDoc, doc)

    def insert_one(self, document: MongoDoc, **kwargs) -> InsertOneResult:
        self._validate_collection()
        self._validate_connections()

        prepared = self._prepare_insert_one_document(document)

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].insert_one(prepared.copy(), **kwargs)
        return result  # type: ignore

    def insert_many(self, documents: list[MongoDoc], **kwargs) -> InsertManyResult:
        self._validate_collection()
        self._validate_connections()

        prepared = self._prepare_insert_many_documents(documents)

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].insert_many(prepared.copy(), **kwargs)
        return result  # type: ignore

    def update_one(self, _filter: dict[str, Any], update: dict[str, Any], **kwargs) -> UpdateResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].update_one(_filter, update, **kwargs)
        return result  # type: ignore

    def update_many(self, _filter: dict[str, Any], update: dict[str, Any], **kwargs) -> UpdateResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].update_many(_filter, update, **kwargs)
        return result  # type: ignore

    def delete_one(self, _filter: dict[str, Any], **kwargs) -> DeleteResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].delete_one(_filter, **kwargs)
        return result  # type: ignore

    def delete_many(self, _filter: dict[str, Any], **kwargs) -> DeleteResult:
        self._validate_collection()
        self._validate_connections()

        collection = cast(str, self.collection)
        for pool in self.pool.pools:
            result = pool.client[pool.database][collection].delete_many(_filter, **kwargs)
        return result  # type: ignore
