from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypeVar

from pymongo.errors import InvalidURI
from pymongo.uri_parser import parse_uri

from ...config.config import MONGODB_MAX_POOLS
from ..defaults import (
    DB_POOL_CONNECTION_TIMEOUT,
    DB_POOL_MAX_CONS,
    DB_POOL_MIN_CONS,
    DB_POOL_RESPONSE_TIMEOUT,
    DB_POOL_SERVER_TIMEOUT,
)
from ..exceptions import MongoPoolConfigurationError, MongoPoolError

ClientT = TypeVar("ClientT")
PoolT = TypeVar("PoolT", bound="BaseMongoPool[Any]")


@dataclass(slots=True)
class BaseMongoPool(Generic[ClientT]):
    name: str
    uri: str
    database: str
    client: ClientT


class BaseMongoPoolManager(ABC, Generic[PoolT, ClientT]):
    def __init__(
        self,
        *,
        min_cons: int = DB_POOL_MIN_CONS,
        max_cons: int = DB_POOL_MAX_CONS,
        srv_timeout: int = DB_POOL_SERVER_TIMEOUT,
        conn_timeout: int = DB_POOL_CONNECTION_TIMEOUT,
        resp_timeout: int = DB_POOL_RESPONSE_TIMEOUT,
    ):
        self._client_config: dict[str, Any] = {
            "minPoolSize": min_cons,
            "maxPoolSize": max_cons,
            "serverSelectionTimeoutMS": srv_timeout,
            "connectTimeoutMS": conn_timeout,
            "socketTimeoutMS": resp_timeout,
            "uuidRepresentation": "standard",
        }
        self._pools: list[PoolT] = []

    @property
    def pools(self) -> list[PoolT]:
        return self._pools

    @property
    def clients(self) -> list[ClientT]:
        return [pool.client for pool in self._pools]

    @property
    def pool_names(self) -> list[str]:
        return [pool.name for pool in self._pools]

    @property
    def _pool_uris(self) -> list[str]:
        return [pool.uri for pool in self._pools]

    def get_pool(self, *, name: Optional[str] = None, uri: Optional[str] = None) -> Optional[PoolT]:
        if name is None and uri is None:
            raise MongoPoolConfigurationError("`name` and `uri` parameters cannot both be empty!\n" "Provide a value for one of them.")

        if name is not None and uri is not None:
            raise MongoPoolConfigurationError("`name` and `uri` parameters cannot both be provided!\n" "Provide only one of them.")

        if name is not None:
            return next((pool for pool in self._pools if pool.name == name), None)
        return next((pool for pool in self._pools if pool.uri == uri), None)

    def get_client(self, *, name: Optional[str] = None, uri: Optional[str] = None) -> Optional[ClientT]:
        pool = self.get_pool(name=name, uri=uri)
        return pool.client if pool is not None else None

    def _register(self, *, name: str, uri: str) -> None:
        if name in self.pool_names or uri in self._pool_uris:
            return

        if len(self._pools) >= MONGODB_MAX_POOLS:
            raise MongoPoolError(f"Maximum MongoDB pools ({MONGODB_MAX_POOLS}) exceeded! " "You cannot register more pools.")

        database = self._parse_database(uri)
        client = self._create_client(uri)

        pool = self._build_pool(
            name=name,
            uri=uri,
            database=database,
            client=client,
        )
        self._pools.append(pool)

    @abstractmethod
    def _create_client(self, uri: str) -> ClientT:
        raise NotImplementedError

    @abstractmethod
    def _build_pool(self, *, name: str, uri: str, database: str, client: ClientT) -> PoolT:
        raise NotImplementedError

    @staticmethod
    def _parse_database(uri: str) -> str:
        try:
            parsed = parse_uri(uri)
        except (InvalidURI, ValueError) as e:
            raise MongoPoolConfigurationError(f"Invalid MongoDB URI provided: {e}") from e

        BaseMongoPoolManager._validate_parsed_uri(parsed)
        return parsed["database"]

    @staticmethod
    def _validate_parsed_uri(uri: dict[str, Any]) -> None:
        if not uri.get("username"):
            raise MongoPoolConfigurationError("Invalid MongoDB URI provided: No username provided.")
        if not uri.get("password"):
            raise MongoPoolConfigurationError("Invalid MongoDB URI provided: No password provided.")
        if not uri.get("database"):
            raise MongoPoolConfigurationError("Invalid MongoDB URI provided: No database provided.")
        if uri.get("options", {}).get("authSource", "") != "admin":
            raise MongoPoolConfigurationError("Invalid MongoDB URI provided: Must always configure the URI to admin source.")
