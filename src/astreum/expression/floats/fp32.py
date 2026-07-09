from struct import pack
from astreum.expression.floats.utils import _unpack_fp32


def _encode_fp32(value: float) -> bytes:
    """Encode fp64 to IEEE 754 fp32 (32-bit)."""
    return pack('<f', value)


def _decode_fp32(data: bytes) -> float:
    """Decode fp32 bytes to fp64."""
    return _unpack_fp32(data)[0]


def fp32_(value: float):
    """Create an FP32 (32-bit float) expression."""
    from astreum.expression.expr import Expr
    return Expr("fp32", value=_encode_fp32(value))
