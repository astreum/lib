from __future__ import annotations

from struct import unpack

from astreum.expression.expr import (
    Expr, NIL, ZERO32, bytes_, link,
    _decode_int,
)
from astreum.expression.floats.common import FLOAT_TAGS
from astreum.expression.floats.fp16 import _decode_fp16
from astreum.expression.floats.bf16 import _decode_bf16


def get_expr_tag(expr: Expr) -> str:
    if expr._tag != "link":
        return expr._tag
    if expr._tail is not None and expr._tail._tag == "symbol":
        return expr._tail._value
    return "link"


def get_expr_value(expr: Expr):
    if expr._value is not None:
        return expr._value
    if expr._tag == "link" and expr._head is not None and expr._head._tag == "bytes":
        return expr._head._value
    raise ValueError("no value")


def get_int_from_expr(expr: Expr) -> int:
    val = get_expr_value(expr)
    if isinstance(val, int):
        return val
    return _decode_int(val)


def get_str_from_expr(expr: Expr) -> str:
    val = get_expr_value(expr)
    if isinstance(val, str):
        return val
    return val.decode("utf-8")


def get_symbol_from_expr(expr: Expr) -> str:
    return get_str_from_expr(expr)


def get_bytes_from_expr(expr: Expr) -> bytes:
    return get_expr_value(expr)


def get_e4m3_from_expr(expr: Expr) -> bytes:
    return get_expr_value(expr)


def get_e5m2_from_expr(expr: Expr) -> bytes:
    return get_expr_value(expr)


def get_fp16_from_expr(expr: Expr) -> float:
    val = get_expr_value(expr)
    if isinstance(val, float):
        return val
    return _decode_fp16(val)


def get_bf16_from_expr(expr: Expr) -> float:
    val = get_expr_value(expr)
    if isinstance(val, float):
        return val
    return _decode_bf16(val)


def get_fp32_from_expr(expr: Expr) -> float:
    val = get_expr_value(expr)
    if isinstance(val, float):
        return val
    return unpack('<f', val)[0]


def get_fp64_from_expr(expr: Expr) -> float:
    val = get_expr_value(expr)
    if isinstance(val, float):
        return val
    return unpack('<d', val)[0]


def bytes_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    result: Expr = NIL
    for value in reversed(items):
        result = link(bytes_(value), result)
    return result


def link_list_to_expr(items: list[bytes]) -> Expr:
    if not items:
        return NIL
    head = Expr("link", head_hash=items[0], tail=NIL)
    current = head
    for value in items[1:]:
        new_link = Expr("link", head_hash=value, tail=NIL)
        current._tail = new_link
        current = new_link
    return head


def exprs_to_linked_expr(items: list[Expr]) -> Expr:
    if not items:
        return NIL
    result: Expr = NIL
    for item in reversed(items):
        result = link(item, result)
    return result


def resolve_list_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    from astreum.storage.get.single import get_expr

    result: list[Expr] = []
    missed: list[bytes] = []
    current = expr
    while current is not None and current._tag == "link":
        if current._head is None and current._head_hash is not None:
            if current._head_hash == ZERO32:
                current._head = NIL
                current._head_hash = None
            else:
                resolved = get_expr(node, current._head_hash)
                if resolved is not None:
                    current._head = resolved
                    current._head_hash = None
                else:
                    missed.append(current._head_hash)
        if current._head is not None:
            result.append(current._head)
        if current._tail is None and current._tail_hash is not None:
            if current._tail_hash == ZERO32:
                current._tail = NIL
                current._tail_hash = None
            else:
                resolved = get_expr(node, current._tail_hash)
                if resolved is not None:
                    current._tail = resolved
                    current._tail_hash = None
                else:
                    missed.append(current._tail_hash)
                    break
        current = current._tail
    return result, missed


def resolve_inner_exprs(node, expr: Expr) -> tuple[list[Expr], list[bytes]]:
    from astreum.storage.get.single import get_expr

    result: list[Expr] = []
    missed: list[bytes] = []

    def _walk(e: Expr) -> None:
        result.append(e)
        if e._tag != "link":
            return
        if e._head is None and e._head_hash is not None:
            resolved = get_expr(node, e._head_hash)
            if resolved is not None:
                e._head = resolved
                e._head_hash = None
            else:
                missed.append(e._head_hash)
        if e._head is not None:
            _walk(e._head)
        if e._tail is None and e._tail_hash is not None:
            resolved = get_expr(node, e._tail_hash)
            if resolved is not None:
                e._tail = resolved
                e._tail_hash = None
            else:
                missed.append(e._tail_hash)
                return
        if e._tail is not None:
            _walk(e._tail)

    _walk(expr)
    return result, missed
