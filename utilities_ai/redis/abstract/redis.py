import os
from abc import ABC
from typing import Optional

from ..._logger import log as _log
from ...exceptions import ConfigurationError
from ...messages.exceptions import undefined_param
from ...messages.warnings import missing_env_var


class BaseStateManager(ABC):
    def __init__(self, db: int, *, host: Optional[str], port: Optional[int]):
        if not host:
            host = os.environ.get("REDIS_HOST")
            if not host:
                raise ConfigurationError(undefined_param.format(name="Redis server host IP", param="REDIS_HOST"))
        else:
            _log.warning(missing_env_var.format(name="Redis server host IP"))

        if not port:
            port_env = os.environ.get("REDIS_PORT")
            if not port_env:
                raise ConfigurationError(undefined_param.format(name="Redis server port", param="REDIS_PORT"))

            try:
                port = int(port_env)
            except ValueError:
                raise ConfigurationError(f"Value `{port_env}` is invalid for `REDIS_PORT`. Must be int.")
        else:
            _log.warning(missing_env_var.format(name="Redis server port"))

        self.host = host
        self.port = port
        self.db = db
