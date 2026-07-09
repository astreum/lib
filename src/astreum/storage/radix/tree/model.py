from __future__ import annotations

from typing import Dict, Optional

from astreum.storage.radix.node import RadixNode


class RadixTree:
    def __init__(
        self,
        root_hash: Optional[bytes] = None,
    ) -> None:
        self.nodes: Dict[bytes, RadixNode] = {}
        self.root_hash = root_hash
