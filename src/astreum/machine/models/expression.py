from blake3 import blake3

ZERO32 = b"\x00" * 32

class Expr:
    class Link:
        def __init__(self, head: 'Expr' = None, tail: 'Expr' = None,
                     head_hash: bytes = None, tail_hash: bytes = None):
            self.head = head
            self.tail = tail
            self.head_hash = head_hash
            self.tail_hash = tail_hash

        def __repr__(self):
            if self.head_hash is not None:
                return f"({self.head_hash.hex()[:8]}# . {self.tail_hash.hex()[:8]}#)"
            return f"({self.head} . {self.tail})"

        def hash(self):
            cached = getattr(self, "_hash", None)
            if cached is not None:
                return cached
            if self.head is None and self.tail is None and self.head_hash is None and self.tail_hash is None:
                self._hash = ZERO32
                return ZERO32
            hh = self.head_hash
            if hh is None:
                hh = self.head.hash() if self.head is not None else ZERO32
            th = self.tail_hash
            if th is None:
                th = self.tail.hash() if self.tail is not None else ZERO32
            content_hash = blake3(hh + th).digest()
            self._hash = blake3(b"\x00" + content_hash).digest()
            return self._hash

        def size(self) -> int:
            cached = getattr(self, "_size", None)
            if cached is not None:
                return cached
            if (self.head is None and self.tail is None
                    and self.head_hash is None and self.tail_hash is None):
                self._size = 64
                return 64
            h = self.head.size() if self.head is not None else 32
            t = self.tail.size() if self.tail is not None else 32
            self._size = h + t
            return self._size

        def to_bytes(self) -> bytes:
            return Expr.to_bytes(self)
            
    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return f"{self.value}"

        def hash(self):
            cached = getattr(self, "_hash", None)
            if cached is not None:
                return cached
            content_hash = blake3(self.value.encode("utf-8")).digest()
            self._hash = blake3(b"\x01" + content_hash).digest()
            return self._hash

        def size(self) -> int:
            return len(self.value.encode("utf-8"))

        def to_bytes(self) -> bytes:
            return Expr.to_bytes(self)
        
    class Bytes:
        def __init__(self, value: bytes):
            self.value = value

        def __repr__(self):
            int_value = int.from_bytes(self.value, "big") if self.value else 0
            return f"{int_value}"

        def hash(self):
            cached = getattr(self, "_hash", None)
            if cached is not None:
                return cached
            content_hash = blake3(self.value).digest()
            self._hash = blake3(b"\x02" + content_hash).digest()
            return self._hash

        def size(self) -> int:
            return len(self.value)

        def to_bytes(self) -> bytes:
            return Expr.to_bytes(self)

    def to_bytes(expr: "Expr") -> bytes:
        """Serialize an Expr to bytes.
        Link: [0x00] [head.hash()] [tail.hash()]  (65 bytes)
        Symbol:  [0x01] [utf-8 value]
        Bytes:   [0x02] [raw bytes]
        """
        if isinstance(expr, Expr.Link):
            hh = expr.head_hash or (expr.head.hash() if expr.head is not None else ZERO32)
            th = expr.tail_hash or (expr.tail.hash() if expr.tail is not None else ZERO32)
            return b"\x00" + hh + th
        if isinstance(expr, Expr.Symbol):
            val = expr.value.encode("utf-8")
            return b"\x01" + val
        if isinstance(expr, Expr.Bytes):
            return b"\x02" + expr.value
        
        raise TypeError("unknown Expr variant")

    def from_bytes(self, data: bytes) -> "Expr":
        if not data:
            raise ValueError("empty bytes")
        tag = data[0]
        if tag == 0x00:
            if len(data) < 65:
                raise ValueError(
                    "Link byte format requires 65 bytes: [1 tag] [32 head] [32 tail]"
                )
            return self.Link(head_hash=data[1:33], tail_hash=data[33:65])
        
        elif tag == 0x01:
            return self.Symbol(data[1:].decode("utf-8"))
        
        elif tag == 0x02:
            return self.Bytes(data[1:])
        
        raise ValueError(f"unknown expression tag: {tag}")


# Sentinel constants
NIL = Expr.Link(None, None)


def bytes_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    result: Expr = Expr.Bytes(items[-1])
    for value in reversed(items[:-1]):
        result = Expr.Link(Expr.Bytes(value), result)
    return result


def link_list_to_expr(items: list[bytes]) -> Expr:
    """Build a forward-ordered linked list of Expr Links from hashes.

    Each item is an existing Expr hash — the chain uses head_hash pointers
    instead of wrapping items in Expr.Bytes. Returns NIL for empty input.
    """
    if not items:
        return NIL
    head = Expr.Link(head_hash=items[0], tail=NIL)
    current = head
    for value in items[1:]:
        new_link = Expr.Link(head_hash=value, tail=NIL)
        current.tail = new_link
        current = new_link
    return head


def resolve_list_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []
    current = expr
    while isinstance(current, Expr.Link):
        if current.head is None and current.head_hash is not None:
            resolved = node.get_expr(current.head_hash)
            if resolved is not None:
                current.head = resolved
                current.head_hash = None
            else:
                missed.append(current.head_hash)
        if current.head is not None:
            result.append(current.head)
        if current.tail is None and current.tail_hash is not None:
            resolved = node.get_expr(current.tail_hash)
            if resolved is not None:
                current.tail = resolved
                current.tail_hash = None
            else:
                missed.append(current.tail_hash)
                break
        current = current.tail
    if not isinstance(current, Expr.Link) and current is not None:
        result.append(current)
    return result, missed


def resolve_inner_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    result: list[Expr] = []
    missed: list[bytes] = []

    def _walk(e: Expr) -> None:
        result.append(e)
        if not isinstance(e, Expr.Link):
            return
        if e.head is None and e.head_hash is not None:
            resolved = node.get_expr(e.head_hash)
            if resolved is not None:
                e.head = resolved
                e.head_hash = None
            else:
                missed.append(e.head_hash)
        if e.head is not None:
            _walk(e.head)
        if e.tail is None and e.tail_hash is not None:
            resolved = node.get_expr(e.tail_hash)
            if resolved is not None:
                e.tail = resolved
                e.tail_hash = None
            else:
                missed.append(e.tail_hash)
                return
        if e.tail is not None:
            _walk(e.tail)

    _walk(expr)
    return result, missed
