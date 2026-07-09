from struct import pack, unpack
from astreum.expression.floats.utils import _unpack_u16, _unpack_fp32

_BF16_TABLE = None


def _bf16_to_fp32(bf16: int) -> float:
    """Convert bf16 bits to fp64 via fp32 intermediate."""
    fp32_bits = bf16 << 16
    return _unpack_fp32(pack('<I', fp32_bits))[0]


def _encode_bf16(value: float) -> bytes:
    """Encode fp64 to BF16 (16-bit brain float).
    Converts to fp32 first, then truncates mantissa to upper 16 bits.
    """
    fp32_bits = unpack('<I', pack('<f', value))[0]
    bf16_bits = fp32_bits >> 16
    return pack('<H', bf16_bits)


def _decode_bf16(data: bytes) -> float:
    """Decode bf16 bytes to fp64 using LUT."""
    return _BF16_TABLE[_unpack_u16(data)[0]]


_BF16_TABLE = [_bf16_to_fp32(i) for i in range(65536)]


def bf16_(value: float):
    """Create a BF16 (16-bit brain float) expression."""
    from astreum.expression.expr import Expr
    return Expr("bf16", value=_encode_bf16(value))
