from __future__ import annotations

from struct import pack, unpack

from blake3 import blake3

from astreum.expression.encoding import encoder

from astreum.expression.floats import (
    e4m3_, e5m2_, fp16_, bf16_, fp32_, fp64_,
    FLOAT_TAGS, _ENCODE_FUNCS, _DECODE_FUNCS,
    _expr_to_fp64, _float_result, _float_to_bytes, _bytes_to_float_expr,
    _FLOAT_TAG_HASHES,
    HASH_SYMBOL_E4M3, HASH_SYMBOL_E5M2, HASH_SYMBOL_FP16,
    HASH_SYMBOL_BF16, HASH_SYMBOL_FP32, HASH_SYMBOL_FP64,
)

ZERO32 = b"\x00" * 32


RESOLUTION_SINGLE = 1
RESOLUTION_LIST = 2
RESOLUTION_FULL = 3

HASH_BYTE_LINK = b"\x00"
HASH_BYTE_SYMBOL = b"\x01"
HASH_BYTE_BYTES = b"\x02"


def _terminal_hash(tag_byte: bytes, data: bytes) -> bytes:
    return blake3(tag_byte + blake3(data).digest()).digest()


def _link_hash(head_hash: bytes, tail_hash: bytes) -> bytes:
    return blake3(HASH_BYTE_LINK + blake3(head_hash + tail_hash).digest()).digest()


def _encode_int(value: int) -> bytes:
    n = max(1, (value.bit_length() + 8) // 8)
    return value.to_bytes(n, "little", signed=True)


def _decode_int(data: bytes) -> int:
    return int.from_bytes(data, "little", signed=True)


# =============================================================================
# Tag encoding/decoding mappings
# =============================================================================

TAG_BYTE_ENCODINGS = {
    "int": _encode_int,
    "str": lambda v: v.encode("utf-8"),
    "symbol": lambda v: v.encode("utf-8"),
    "bytes": lambda v: v,
    "e4m3": lambda v: v,  # already bytes
    "e5m2": lambda v: v,
    "fp16": lambda v: v,
    "bf16": lambda v: v,
    "fp32": lambda v: v,
    "fp64": lambda v: pack('<d', v),
}

TAG_BYTE_DECODINGS = {
    "int": _decode_int,
    "str": lambda d: d.decode("utf-8"),
    "symbol": lambda d: d.decode("utf-8"),
    "bytes": lambda d: d,
    "e4m3": lambda d: d,  # return bytes as-is
    "e5m2": lambda d: d,
    "fp16": lambda d: d,
    "bf16": lambda d: d,
    "fp32": lambda d: d,
    "fp64": lambda d: unpack('<d', d)[0],
}

TAG_SYMBOL_BYTES = {
    "int": b"int",
    "str": b"str",
    "symbol": b"symbol",
    "bytes": b"bytes",
    "e4m3": b"e4m3",
    "e5m2": b"e5m2",
    "fp16": b"fp16",
    "bf16": b"bf16",
    "fp32": b"fp32",
    "fp64": b"fp64",
}

# Hash constants for non-float types
HASH_SYMBOL_INT = _terminal_hash(HASH_BYTE_SYMBOL, b"int")
HASH_SYMBOL_STR = _terminal_hash(HASH_BYTE_SYMBOL, b"str")
HASH_SYMBOL_SYMBOL = _terminal_hash(HASH_BYTE_SYMBOL, b"symbol")
HASH_SYMBOL_BYTES = _terminal_hash(HASH_BYTE_SYMBOL, b"bytes")

# Mapping for hash computation
_FLOAT_TAG_HASHES = {
    "e4m3": HASH_SYMBOL_E4M3,
    "e5m2": HASH_SYMBOL_E5M2,
    "fp16": HASH_SYMBOL_FP16,
    "bf16": HASH_SYMBOL_BF16,
    "fp32": HASH_SYMBOL_FP32,
    "fp64": HASH_SYMBOL_FP64,
}


class Expr:
    __slots__ = ("_tag", "_value", "_head", "_tail", "_head_hash", "_tail_hash", "_hash", "_size")

    def __init__(self, tag, value=None, head=None, tail=None, head_hash=None, tail_hash=None):
        self._tag = tag
        self._value = value
        self._head = head
        self._tail = tail
        self._head_hash = head_hash
        self._tail_hash = tail_hash
        self._hash = None
        self._size = None

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = v

    def __repr__(self):
        if self._tag == "int":
            return str(self._value)
        elif self._tag in FLOAT_TAGS:
            # Decode to fp64 for display
            return str(_expr_to_fp64(self))
        elif self._tag == "str":
            return f'"{self._value}"'
        elif self._tag == "symbol":
            return self._value
        elif self._tag == "bytes":
            if self._value is None:
                return "0"
            if not self._value:
                return "0"
            int_val = _decode_int(self._value)
            return f"{int_val}"
        elif self._tag == "link":
            if self._head_hash is not None:
                return f"({self._head_hash.hex()[:8]}# . {self._tail_hash.hex()[:8]}#)"
            return f"({self._head} . {self._tail})"
        else:
            return f"#<{self._tag} {self._value}>"

    def _hash_of_encoded(self) -> bytes:
        encoder = TAG_BYTE_ENCODINGS.get(self._tag)
        if encoder is None:
            return self._value.hash() if self._value is not None else ZERO32
        return _terminal_hash(HASH_BYTE_BYTES, encoder(self._value))

    def hash(self):
        if self._hash is not None:
            return self._hash

        if self._tag == "link":
            hh = self._head_hash
            if hh is None:
                hh = self._head.hash() if self._head is not None else ZERO32
            th = self._tail_hash
            if th is None:
                th = self._tail.hash() if self._tail is not None else ZERO32
            self._hash = _link_hash(hh, th)
            return self._hash

        if self._tag == "symbol":
            self._hash = _terminal_hash(HASH_BYTE_SYMBOL, self._value.encode("utf-8"))
            return self._hash

        if self._tag == "bytes":
            self._hash = _terminal_hash(HASH_BYTE_BYTES, self._value)
            return self._hash

        if self._tag in TAG_SYMBOL_BYTES:
            head_hash = _terminal_hash(HASH_BYTE_BYTES, TAG_BYTE_ENCODINGS[self._tag](self._value))
            # Use dict lookup instead of chained ternary
            tail_hash = _FLOAT_TAG_HASHES.get(self._tag) if self._tag in FLOAT_TAGS else (
                HASH_SYMBOL_INT if self._tag == "int" else (
                    HASH_SYMBOL_STR if self._tag == "str" else HASH_SYMBOL_BYTES
                )
            )
            self._hash = _link_hash(head_hash, tail_hash)
            return self._hash

        head_hash = self._value.hash() if self._value is not None else ZERO32
        tail_hash = _terminal_hash(HASH_BYTE_SYMBOL, self._tag.encode("utf-8"))
        self._hash = _link_hash(head_hash, tail_hash)
        return self._hash

    def size(self):
        if self._size is not None:
            return self._size

        if self._tag == "link":
            h = self._head.size() if self._head is not None else 32
            if self._head_hash is not None:
                h = 32
            t = self._tail.size() if self._tail is not None else 32
            if self._tail_hash is not None:
                t = 32
            self._size = h + t
            return self._size

        encoder = TAG_BYTE_ENCODINGS.get(self._tag)
        if encoder is not None:
            self._size = len(encoder(self._value))
            return self._size

        if self._value is not None:
            self._size = self._value.size()
            return self._size

        self._size = 0
        return 0

    def resolution(self) -> int:
        if self._tag != "link":
            return RESOLUTION_SINGLE
        hh = self._head_hash
        if hh is None:
            hh = self._head.hash() if self._head is not None else ZERO32
        if hh == ZERO32:
            return RESOLUTION_LIST
        return RESOLUTION_FULL

    

    


def int_(value: int) -> Expr:
    return Expr("int", value=value)


def str_(value: str) -> Expr:
    return Expr("str", value=value)


def symbol(value: str) -> Expr:
    return Expr("symbol", value=value)


def bytes_(value: bytes) -> Expr:
    return Expr("bytes", value=value)


def link(head, tail) -> Expr:
    return Expr("link", head=head, tail=tail)


def collect_list(expr: Expr) -> list:
    """Walk tail chain, collect all elements including root."""
    result = [expr]
    current = expr
    while current._tag == "link" and current._tail is not None:
        current = current._tail
        result.append(current)
    return result


def collect_full(expr: Expr) -> list:
    """Walk tree, collect all sub-exprs (deduped by hash)."""
    result = []
    visited = set()

    def _walk(e):
        if e is None:
            return
        h = e.hash()
        if h in visited:
            return
        visited.add(h)
        result.append(e)
        if e._tag == "link":
            _walk(e._head)
            _walk(e._tail)

    _walk(expr)
    return result


NIL = link(None, None)
