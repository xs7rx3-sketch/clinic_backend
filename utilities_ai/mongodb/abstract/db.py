from abc import ABC
from typing import Any, Generic, Optional, Sequence, TypeAlias, TypeVar

from bson import ObjectId

from ..._logger import log as _log
from ..exceptions import MongoConfigurationError, MongoError
from .pool import BaseMongoPoolManager, PoolT

MongoDoc: TypeAlias = dict[str, Any]


PoolManagerT = TypeVar("PoolManagerT", bound="BaseMongoPoolManager[Any, Any]")


class BaseMongoDB(ABC, Generic[PoolManagerT, PoolT]):
    def __init__(self, pool: PoolManagerT, *, collection: Optional[str] = None):
        if not pool.pools:
            _log.warning("MongoDB instance initialized with no pool connections!")

        self.pool = pool
        self._collection = collection

    @property
    def collection(self) -> Optional[str]:
        return self._collection

    @collection.setter
    def collection(self, collection: str):
        self._collection = collection

    def _validate_collection(self):
        if not self.collection:
            raise MongoConfigurationError("Database collection was not specified.")

    def _validate_connections(self) -> None:
        if not self.pool.pools:
            raise MongoConfigurationError("Cannot perform the operation when no pools are initialized.")

    def _get_primary_pool(self) -> PoolT:
        self._validate_connections()
        return self.pool.pools[0]

    @staticmethod
    def _prepare_insert_one_document(document: MongoDoc) -> MongoDoc:
        prepared = document.copy()
        prepared.setdefault("_id", ObjectId())
        return prepared

    @staticmethod
    def _prepare_insert_many_documents(documents: list[MongoDoc]) -> list[MongoDoc]:
        prepared_documents: list[MongoDoc] = []

        for document in documents:
            prepared = document.copy()
            prepared.setdefault("_id", ObjectId())
            prepared_documents.append(prepared)

        return prepared_documents

    def _catch_mongo_exception(
        self,
        result: Sequence[Any | BaseException],
        *,
        pools: Sequence[PoolT],
    ) -> None:
        for index, item in enumerate(result):
            if isinstance(item, Exception):
                raise MongoError(f"MongoDB exception raised from pool {pools[index].name}:\n{item}") from item
