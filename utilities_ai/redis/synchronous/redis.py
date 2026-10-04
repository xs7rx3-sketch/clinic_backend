import pickle
from typing import Any, Optional

import redis

from ..abstract.redis import BaseStateManager
from ..defaults import REDIS_DATABASE


# TODO: Add useful logs that can be disabled.
class StateManager(BaseStateManager):
    def __init__(self, db: int = REDIS_DATABASE, *, host: Optional[str] = None, port: Optional[int] = None):
        super().__init__(db, host=host, port=port)

        self.redis = redis.Redis(host=self.host, port=self.port, db=self.db, decode_responses=False)

    def store_state(self, key: str, value: Any):
        serialized = pickle.dumps(value)
        self.redis.set(key, serialized)

    def fetch_state(self, key: str) -> Optional[Any]:
        serialized = self.redis.get(key)
        return pickle.loads(serialized) if serialized else None  # type: ignore

    def reset_state(self, key: Optional[str] = None, all_states: bool = False):
        if not all_states and key is None:
            return

        if all_states:
            self.redis.flushdb()
            return

        self.redis.delete(key)  # type: ignore

    def close(self):
        self.redis.close()
