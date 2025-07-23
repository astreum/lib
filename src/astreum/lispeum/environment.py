from typing import Dict, Optional
import uuid

from astreum.lispeum.expression import Expr


class Env:
    def __init__(
        self,
        data: Optional[Dict[str, Expr]] = None,
        parent_id: Optional[uuid.UUID] = None,
        max_exprs: Optional[int] = 8,
    ):
        self.data: Dict[str, Expr] = data if data is not None else {}
        self.parent_id: Optional[uuid.UUID] = parent_id
        self.max_exprs: Optional[int] = max_exprs

    def put(self, name: str, value: Expr) -> None:
        if (
            self.max_exprs is not None
            and name not in self.data
            and len(self.data) >= self.max_exprs
        ):
            raise RuntimeError(
                f"environment full: {len(self.data)} ≥ max_exprs={self.max_exprs}"
            )
        self.data[name] = value

    def get(self, name: str) -> Optional[Expr]:
        return self.data.get(name)

    def pop(self, name: str) -> Optional[Expr]:
        return self.data.pop(name, None)

    def __repr__(self) -> str:
        return (
            f"Env(size={len(self.data)}, "
            f"max_exprs={self.max_exprs}, "
            f"parent_id={self.parent_id})"
        )
