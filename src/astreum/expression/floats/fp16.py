from struct import pack
from astreum.expression.floats.utils import _unpack_fp16


def _encode_fp16(value: float) -> bytes:
    """Encode fp64 to IEEE 754 fp16 (16-bit) using struct."""
    return pack('<e', value)


def _decode_fp16(data: bytes) -> float:
    """Decode fp16 bytes to fp64."""
    return _unpack_fp16(data)[0]


def fp16_(value: float):
    """Create an FP16 (16-bit float) expression."""
    from astreum.expression.expr import Expr, FP16_SYMBOL
    return Expr("link", value=_encode_fp16(value), tail=FP16_SYMBOL)
