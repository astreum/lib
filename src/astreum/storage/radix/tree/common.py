from __future__ import annotations

from typing import Optional, Union

from ....machine.models.expression import Expr
from ..node import RadixNode


def _make_node(
    prefix_bits: bytes,
    prefix_len: int,
    value: Optional[Union[Expr, bytes]],
    child0: Optional[bytes],
    child1: Optional[bytes],
) -> RadixNode:
    return RadixNode(prefix_len, prefix_bits, value, child0, child1)
