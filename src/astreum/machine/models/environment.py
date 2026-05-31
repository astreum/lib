from ast import Expr
from typing import Dict, Optional

class Env:
    def __init__(self, data: Dict[str, Expr] = {}, parent: "Env" = None):
        self.data = data
        self.parent = parent

    def get(self, key: str) -> Optional[Expr]:
        if key in self.data:
            return self.data[key]
        if self.parent:
            return self.parent.get(key=key)
        return None

    def put(self, key: str, value: Expr):
        self.data[key] = value
