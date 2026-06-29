from __future__ import annotations

from struct import pack, unpack

from blake3 import blake3

ZERO32 = b"\x00" * 32

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


def _encode_float(value: float) -> bytes:
    return pack("<d", value)


def _decode_float(data: bytes) -> float:
    return unpack("<d", data)[0]


TAG_BYTE_ENCODINGS = {
    "int": _encode_int,
    "float": _encode_float,
    "str": lambda v: v.encode("utf-8"),
    "symbol": lambda v: v.encode("utf-8"),
    "bytes": lambda v: v,
}

TAG_BYTE_DECODINGS = {
    "int": _decode_int,
    "float": _decode_float,
    "str": lambda d: d.decode("utf-8"),
    "symbol": lambda d: d.decode("utf-8"),
    "bytes": lambda d: d,
}

TAG_SYMBOL_BYTES = {
    "int": b"int",
    "float": b"float",
    "str": b"str",
    "symbol": b"symbol",
    "bytes": b"bytes",
}

HASH_SYMBOL_INT = _terminal_hash(HASH_BYTE_SYMBOL, b"int")
HASH_SYMBOL_FLOAT = _terminal_hash(HASH_BYTE_SYMBOL, b"float")
HASH_SYMBOL_STR = _terminal_hash(HASH_BYTE_SYMBOL, b"str")
HASH_SYMBOL_SYMBOL = _terminal_hash(HASH_BYTE_SYMBOL, b"symbol")
HASH_SYMBOL_BYTES = _terminal_hash(HASH_BYTE_SYMBOL, b"bytes")


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
        elif self._tag == "float":
            return str(self._value)
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
            tail_hash = HASH_SYMBOL_INT if self._tag == "int" else (
                HASH_SYMBOL_FLOAT if self._tag == "float" else (
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

    def to_bytes(self) -> bytes:
        if self._tag == "link":
            hh = self._head_hash
            if hh is None:
                hh = self._head.hash() if self._head is not None else ZERO32
            th = self._tail_hash
            if th is None:
                th = self._tail.hash() if self._tail is not None else ZERO32
            return b"\x00" + hh + th

        if self._tag == "symbol":
            val = self._value.encode("utf-8")
            return b"\x01" + val

        if self._tag == "bytes":
            return b"\x02" + self._value

        encoder = TAG_BYTE_ENCODINGS.get(self._tag)
        if encoder is not None:
            head = Expr("bytes", value=encoder(self._value))
            tail = Expr("symbol", value=self._tag)
            return link(head, tail).to_bytes()

        head = self._value if self._value is not None else link(None, None)
        tail = Expr("symbol", value=self._tag)
        return link(head, tail).to_bytes()

    @staticmethod
    def from_bytes(data: bytes) -> Expr:
        if not data:
            raise ValueError("empty bytes")
        tag = data[0]
        if tag == 0x00:
            if len(data) < 65:
                raise ValueError("link requires 65 bytes")
            return Expr("link", head_hash=data[1:33], tail_hash=data[33:65])
        elif tag == 0x01:
            return Expr("symbol", value=data[1:].decode("utf-8"))
        elif tag == 0x02:
            return Expr("bytes", value=data[1:])
        else:
            raise ValueError(f"unknown wire tag: {tag}")


def int_(value: int) -> Expr:
    return Expr("int", value=value)


def float_(value: float) -> Expr:
    return Expr("float", value=value)


def str_(value: str) -> Expr:
    return Expr("str", value=value)


def symbol(value: str) -> Expr:
    return Expr("symbol", value=value)


def bytes_(value: bytes) -> Expr:
    return Expr("bytes", value=value)


def link(head, tail) -> Expr:
    return Expr("link", head=head, tail=tail)


NIL = link(None, None)
