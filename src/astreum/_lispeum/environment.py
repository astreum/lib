from ast import Expr
from typing import Dict, Optional
import uuid


class Env:
    def __init__(
        self,
        data: Optional[Dict[str, Expr]] = None,
        parent_id: Optional[uuid.UUID] = None,
    ):
        self.data: Dict[bytes, Expr] = {} if data is None else data
        self.parent_id = parent_id