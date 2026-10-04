import os
from typing import Optional

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from ..._logger import log as _log
from ...exceptions import ConfigurationError
from ...messages.exceptions import undefined_param
from ...messages.warnings import missing_env_var
from ..defaults import DB_POOL_MAX_CONS, DB_POOL_MIN_CONS, DB_POOL_TIMEOUT
from ..exceptions import PostgresConfigurationError

_pool: AsyncConnectionPool | None = None


async def init_pool(
    uri: Optional[str] = None, *, min_cons: int = DB_POOL_MIN_CONS, max_cons: int = DB_POOL_MAX_CONS, timeout: int = DB_POOL_TIMEOUT
):
    global _pool
    if _pool:
        return

    if not uri:
        uri = os.environ.get("POSTGRES_URI")
        if not uri:
            raise ConfigurationError(undefined_param.format(name="PostgreSQL URI", param="POSTGRES_URI"))
    else:
        _log.warning(missing_env_var.format(name="PostgreSQL URI"))

    _pool = AsyncConnectionPool(
        uri,
        min_size=min_cons,
        max_size=max_cons,
        timeout=timeout,
        open=False,
        check=AsyncConnectionPool.check_connection,
        kwargs={"row_factory": dict_row},
    )
    await _pool.open(wait=True)


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> AsyncConnectionPool:
    if not _pool:
        raise PostgresConfigurationError("Postgres pool is not initiated!\nYou must initiate the pool through `init_pool()` function.")
    return _pool
