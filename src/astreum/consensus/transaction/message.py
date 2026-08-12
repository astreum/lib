from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from astreum.expression import Expr, NIL, ZERO32, link
from astreum.expression.expr import (
    TAG_BYTE_ENCODINGS,
    TAG_BYTE_DECODINGS,
    TYPE_SYMBOLS,
    _get_head_hash,
    _get_tail_hash,
)
from astreum.communication.storage_response.storage_found import STORAGE_FOUND_PAYLOAD

if TYPE_CHECKING:
    from astreum.consensus.transaction.model import Transaction


_SCALAR_TYPES = [name for name in TAG_BYTE_ENCODINGS if name in TYPE_SYMBOLS]
_SCALAR_INDEX = {name: i for i, name in enumerate(_SCALAR_TYPES)}
_SCALAR_NAMES = {i: name for i, name in enumerate(_SCALAR_TYPES)}

# Expr wire tags (lossless superset of the storage framing: a scalar tag
# carries the typed value inline so the whole tree round-trips in-memory).
_TAG_LINK = 0x00
_TAG_SYMBOL = 0x01
_TAG_BYTES = 0x02
_TAG_SCALAR = 0x03


def encode_transaction_message(tx_exprs: List[Expr]) -> bytes:
    """Encode the whole resolved tx tree as a TRANSACTION message payload.

    ``tx_exprs`` is the output of ``resolve_inner_exprs(node, transaction.expr())``
    with the header root first. Uses the storage_found length-prefixed list
    framing; each expr is encoded losslessly (typed scalars inline).
    """
    parts = [bytes([STORAGE_FOUND_PAYLOAD])]
    for expr in tx_exprs:
        expr_bytes = _encode_expr(expr)
        parts.append(len(expr_bytes).to_bytes(4, "big", signed=False))
        parts.append(expr_bytes)
    return b"".join(parts)


def decode_transaction_message(content: bytes) -> Optional["Transaction"]:
    """Decode a TRANSACTION message payload into a fully-linked Transaction.

    Pure in-memory — zero storage reads/writes. Returns None on any structural
    or parse failure.
    """
    if not content:
        return None
    if content[0] != STORAGE_FOUND_PAYLOAD:
        return None
    try:
        exprs = _decode_payload(content[1:])
    except Exception:
        return None
    if not exprs:
        return None

    expr_map: dict[bytes, Expr] = {e.hash(): e for e in exprs}

    root = exprs[0]
    if root.base != "link":
        return None

    try:
        _link_tree(root, expr_map)
    except KeyError:
        return None

    if root.tail is None or not (root.tail.base == "symbol" and root.tail.value == "transaction"):
        return None

    try:
        return _parse_transaction(root)
    except Exception:
        return None


def _encode_expr(expr: Expr) -> bytes:
    if expr.base == "link":
        if (
            expr.value is not None
            and expr.tail is not None
            and expr.tail.base == "symbol"
            and expr.tail.value in _SCALAR_INDEX
        ):
            encoder = TAG_BYTE_ENCODINGS[expr.tail.value]
            return (
                bytes([_TAG_SCALAR, _SCALAR_INDEX[expr.tail.value]])
                + encoder(expr.value)
            )
        return b"\x00" + _get_head_hash(expr) + _get_tail_hash(expr)

    if expr.base == "symbol":
        return b"\x01" + expr.value.encode("utf-8")

    if expr.base == "bytes":
        return b"\x02" + expr.value

    raise TypeError(f"cannot encode expr base: {expr.base}")


def _decode_expr(data: bytes) -> Expr:
    if not data:
        raise ValueError("empty expr bytes")
    tag = data[0]
    if tag == _TAG_LINK:
        if len(data) < 65:
            raise ValueError("link requires 65 bytes")
        return Expr("link", head_hash=data[1:33], tail_hash=data[33:65])
    if tag == _TAG_SYMBOL:
        return Expr("symbol", value=data[1:].decode("utf-8"))
    if tag == _TAG_BYTES:
        return Expr("bytes", value=data[1:])
    if tag == _TAG_SCALAR:
        if len(data) < 2:
            raise ValueError("scalar requires type byte")
        name = _SCALAR_NAMES[data[1]]
        value = TAG_BYTE_DECODINGS[name](data[2:])
        return Expr("link", value=value, tail=TYPE_SYMBOLS[name])
    raise ValueError(f"unknown expr wire tag: {tag}")


def _decode_payload(payload: bytes) -> List[Expr]:
    exprs: List[Expr] = []
    offset = 0
    while offset < len(payload):
        if len(payload) - offset < 4:
            raise ValueError("truncated expr length")
        expr_len = int.from_bytes(payload[offset : offset + 4], "big", signed=False)
        offset += 4
        if expr_len <= 0:
            raise ValueError("invalid expr length")
        end = offset + expr_len
        if end > len(payload):
            raise ValueError("truncated expr payload")
        exprs.append(_decode_expr(payload[offset:end]))
        offset = end
    return exprs


def _link_tree(root: Expr, expr_map: dict[bytes, Expr]) -> None:
    """Back-fill every ``head_hash``/``tail_hash`` from the decoded set so the
    tree is fully linked in-memory and resolution never touches storage."""
    visited = set()

    def _link(e: Expr) -> None:
        if e is None or e.base != "link":
            return
        if id(e) in visited:
            return
        visited.add(id(e))

        if e.head is None:
            if e.head_hash is not None:
                if e.head_hash == ZERO32:
                    e.head = NIL
                else:
                    e.head = expr_map[e.head_hash]
                e.head_hash = None
        if e.tail is None:
            if e.tail_hash is not None:
                if e.tail_hash == ZERO32:
                    e.tail = None
                else:
                    e.tail = expr_map[e.tail_hash]
                e.tail_hash = None

        if e.head is not None:
            _link(e.head)
        if e.tail is not None:
            _link(e.tail)

    _link(root)


def _list_items(head: Expr) -> List[Expr]:
    """Storage-free analogue of resolve_list_exprs: return the head of each
    link in the chain (works only on a fully-linked tree)."""
    result: List[Expr] = []
    current = head
    while current is not None and current.base == "link":
        if current.head is not None:
            result.append(current.head)
        current = current.tail
    return result


def _parse_transaction(root: Expr) -> "Transaction":
    """Storage-free analogue of get_transaction_from_storage. The tree is fully
    linked, so only structural/type validation happens here."""
    from astreum.consensus.transaction.code import TransactionCode
    from astreum.consensus.transaction.model import Transaction

    inner = root.head
    if inner is None or inner.base != "link":
        raise ValueError("transaction inner header must be a Link")

    inner_nodes = _list_items(inner)
    if len(inner_nodes) != 2:
        raise ValueError("malformed transaction header length")

    body, sig = inner_nodes
    if sig.base != "bytes":
        raise ValueError("invalid transaction signature: expected Bytes")
    signature_bytes = sig.value
    if body.base != "link":
        raise ValueError("transaction body must be a Link chain")

    body_nodes = _list_items(body)
    if len(body_nodes) != 8:
        raise ValueError("malformed transaction body length")

    (
        amount_node,
        chain_id_node,
        code_node,
        cost_limit_node,
        counter_node,
        data_node,
        recipient_node,
        sender_node,
    ) = body_nodes

    if amount_node._tag != "int":
        raise ValueError("expected Int for amount")
    if chain_id_node._tag != "int":
        raise ValueError("expected Int for chain_id")
    if code_node._tag != "int":
        raise ValueError("expected Int for code")
    if cost_limit_node._tag != "int":
        raise ValueError("expected Int for cost_limit")
    if counter_node._tag != "int":
        raise ValueError("expected Int for counter")
    if recipient_node._tag != "bytes":
        raise ValueError("expected Bytes for recipient")
    if sender_node._tag != "bytes":
        raise ValueError("expected Bytes for sender")

    tx_hash = root.hash()
    tx = Transaction(
        chain_id=chain_id_node.value,
        amount=amount_node.value,
        code=TransactionCode(code_node.value),
        counter=counter_node.value,
        cost_limit=cost_limit_node.value,
        data=data_node,
        recipient=recipient_node.value,
        sender=sender_node.value,
        signature=signature_bytes,
        body_hash=body.hash(),
        expr_id=tx_hash,
        hash=tx_hash,
    )
    tx._expr = root
    return tx
