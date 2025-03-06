from typing import Dict, Optional
from astreum.lispeum.expression import Expr


class Environment:
    def __init__(self, parent: 'Environment' = None, node: 'Node' = None):
        self.data: Dict[str, Expr] = {}
        self.parent = parent
        self.node = node

    def set(self, name: str, value: Expr):
        if self.node:
            self.node.post_global_storage(name, value)
        else:
            self.data[name] = value

    def get(self, name: str) -> Optional[Expr]:
        if self.node:
            return self.node.query_global_storage(name)

        if name in self.data:
            return self.data[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            return None

    def __repr__(self):
        return f"Environment({self.data})"
