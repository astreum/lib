from typing import Dict, Optional
from astreum.machine.expression import Expr


class Environment:
    def __init__(self, parent: 'Environment' = None):
        self.data: Dict[str, Expr] = {}
        self.parent = parent

    def set(self, name: str, value: Expr):
        self.data[name] = value

    def get(self, name: str) -> Optional[Expr]:
        if name in self.data:
            return self.data[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            return None

    def __repr__(self):
        return f"Environment({self.data})"
