"""Initialize and configure checkpoint storage for LangGraph workflow execution.

This module provides factory functions for creating checkpoint savers that store
workflow state at different granularities. Supported backends include in-memory
storage for development and PostgreSQL for production use.

Note:
    PostgreSQL configuration requires either a `postgres_uri` parameter or
    a `POSTGRES_URI` environment variable. The connection pool is opened
    asynchronously and should not be closed by the caller.

Example:
    >>> checkpointer = await init_checkpointer("ram")
    >>> checkpointer = await init_checkpointer("postgres")
"""

import os
from typing import Literal, Optional, TypeAlias

from langgraph.checkpoint.base import SerializerProtocol
from langgraph.checkpoint.memory import MemorySaver
try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except ImportError:
    AsyncPostgresSaver = None
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.types import Checkpointer
from psycopg_pool import AsyncConnectionPool

from ..._logger import log as _log
from ...exceptions import ConfigurationError
from ...messages.exceptions import undefined_param
from ...messages.warnings import missing_env_var

MemoryTypes: TypeAlias = Literal["ram", "postgres", None]  # Supported checkpoint storage backends


async def init_checkpointer(
    memory: MemoryTypes, *, postgres_uri: Optional[str] = None, serializer: Optional[SerializerProtocol] = None
) -> Optional[Checkpointer]:
    """Initialize a checkpoint saver for LangGraph workflow state persistence.

    Creates and returns a configured checkpoint saver based on the memory type.
    For PostgreSQL, opens an async connection pool with the provided or
    environment-configured URI. The checkpointer is configured with the
    specified serializer before being returned.

    Args:
        memory: The checkpoint backend type. `"ram"` uses in-memory storage,
            `"postgres"` uses PostgreSQL, `None` disables checkpointing.
        postgres_uri: PostgreSQL connection string. If not provided and
            `memory` is `"postgres"`, falls back to the `POSTGRES_URI`
            environment variable. Defaults to `None`.
        serializer: Serializer protocol for checkpoint serialization. If
            `None`, defaults to `JsonPlusSerializer(pickle_fallback=True)`.
            Defaults to `None`.

    Returns:
        A `Checkpointer` instance configured with the specified serializer
        for the given backend, or `None` if `memory` is `None`.

    Raises:
        ConfigurationError: If `memory` is `"postgres"` but no `postgres_uri`
            is provided and the `POSTGRES_URI` environment variable is unset.

    Example:
        >>> checkpointer = await init_checkpointer("ram")
        >>> checkpointer is not None
        True
        >>> none_checkpointer = await init_checkpointer(None)
        >>> none_checkpointer is None
        True

    Note:
        This function is async because PostgreSQL pool initialization requires
        awaiting the connection pool opening. The returned checkpointer should
        be passed directly to LangGraph graph execution without manual closing.
    """

    if serializer is None:
        serializer = JsonPlusSerializer(pickle_fallback=True)

    if memory is None:
        return None

    if memory == "ram":
        checkpointer = MemorySaver()

    elif memory == "postgres":
        if AsyncPostgresSaver is None:
            raise ConfigurationError(
                "PostgreSQL checkpointing requires 'langgraph-checkpoint-postgres'. "
                "Install it using: pip install langgraph-checkpoint-postgres"
            )
        if not postgres_uri:
            postgres_uri = os.environ.get("POSTGRES_URI")
            if not postgres_uri:
                raise ConfigurationError(undefined_param.format(name="PostgreSQL URI", param="POSTGRES_URI"))
        else:
            _log.warning(missing_env_var.format(name="PostgreSQL URI"))

        pool = AsyncConnectionPool(postgres_uri, open=False)
        await pool.open(wait=True)
        checkpointer = AsyncPostgresSaver(pool)

    checkpointer.serde = serializer
    return checkpointer
