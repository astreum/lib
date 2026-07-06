from struct import pack
from .utils import _unpack_fp16


def _encode_fp16(value: float) -> bytes:
    """Encode fp64 to IEEE 754 fp16 (16-bit) using struct."""
    return pack('<e', value)


def _decode_fp16(data: bytes) -> float:
    """Decode fp16 bytes to fp64."""
    return _unpack_fp16(data)[0]


def fp16_(value: float):
    """Create an FP16 (16-bit float) expression."""
    from ..expr import Expr
    return Expr("fp16", value=_encode_fp16(value))
