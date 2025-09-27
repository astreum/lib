from ast import Expr
from typing import Dict, Optional


class Env:
    def __init__(
        self,
        data: Optional[Dict[str, Expr]] = None
    ):
        self.data: Dict[bytes, Expr] = {} if data is None else data