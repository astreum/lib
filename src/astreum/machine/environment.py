# Define the Environment class
from typing import Callable, Dict, List, Optional
from src.astreum.machine.expression import Expr


class Environment:
    def __init__(self, parent: 'Environment' = None):
        self.data: Dict[str, Expr] = {}
        self.parent = parent

    def set(self, name: str, value: Expr):
        """Set a variable in the current environment."""
        self.data[name] = value

    def get(self, name: str) -> Optional[Expr]:
        """Retrieve a variable's value, searching parent environments if necessary."""
        if name in self.data:
            return self.data[name]
        elif self.parent:
            return self.parent.get(name)
        else:
            return None

    def __repr__(self):
        return f"Environment({self.data})"
