from __future__ import annotations

from typing import Optional, Union

from astreum.expression import Expr


class RadixNode:
    def __init__(
        self,
        key_len: int,
        key: bytes,
        value: Optional[Union[Expr, bytes]],
        child_0: Optional[bytes],
        child_1: Optional[bytes]
    ):
        self.key_len = key_len
        self.key = key
        self.value = value
        self.child_0 = child_0
        self.child_1 = child_1
        self._hash: Optional[bytes] = None
        self._expr: Optional["Expr"] = None
