from ast import Expr
from typing import Dict, Optional
import uuid


class Env:
    def __init__(
        self,
        data: Optional[Dict[str, Expr]] = None,
        parent_id: Optional[uuid.UUID] = None,
    ):
        self.data: Dict[str, Expr] = {} if data is None else data
        self.parent_id = parent_id

def env_get(self, env_id: uuid.UUID, key: str) -> Optional[Expr]:
    """Resolve a value by walking the environment chain starting at env_id."""
    cur = self.environments.get(env_id)
    while cur is not None:
        if key in cur.data:
            return cur.data[key]
        cur = self.environments.get(cur.parent_id) if cur.parent_id else None
    return None

def env_set(self, env_id: uuid.UUID, key: str, value: Expr) -> bool:
    """Bind a value to key within the specified environment if it exists."""
    with self.machine_environments_lock:
        env = self.environments.get(env_id)
        if env is None:
            return False
        env.data[key] = value
        return True
