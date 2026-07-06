from math import isnan, isinf, log2, floor

_E5M2_TABLE = None

def _e5m2_to_fp64(b: int) -> float:
    """Decode E5M2 (5-bit exponent, 2-bit mantissa, 8-bit float) to fp64.
    
    Format: s eeeee mm
    - s: sign bit (bit 7)
    - eeeee: 5-bit exponent (bits 6-2), biased by 15
    - mm: 2-bit mantissa (bits 1-0)
    - Exponent 0b00000: zero or subnormal
    - Exponent 0b11111: infinity or NaN
    """
    sign = -1.0 if (b & 0x80) else 1.0
    exp = (b >> 2) & 0x1F
    mantissa = b & 0x03
    
    if exp == 0:
        if mantissa == 0:
            return 0.0 if (b & 0x80) == 0 else -0.0
        return sign * (2 ** -14) * (mantissa / 4.0)
    elif exp == 0x1F:
        if mantissa == 0:
            return float('inf') if (b & 0x80) == 0 else float('-inf')
        else:
            return float('nan')
    else:
        return sign * (2 ** (exp - 15)) * (1.0 + mantissa / 4.0)


def _encode_e5m2(value: float) -> bytes:
    """Encode fp64 to E5M2 (8-bit)."""
    if isnan(value):
        return b'\x7f'
    if value == float('inf'):
        return b'\x7c'
    if value == float('-inf'):
        return b'\xfc'
    
    sign = 0x80 if value < 0 else 0x00
    abs_val = abs(value)
    
    if abs_val == 0.0:
        return bytes([sign])
    
    logv = log2(abs_val)
    exp_unbiased = int(floor(logv)) + 15
    exp_unbiased = max(1, min(exp_unbiased, 30))
    
    mantissa_val = abs_val / (2 ** (exp_unbiased - 15)) - 1.0
    mantissa = int(round(mantissa_val * 4))
    if mantissa >= 4:
        mantissa = 3
    
    encoded = sign | (exp_unbiased << 2) | mantissa
    return bytes([encoded])


_E5M2_TABLE = [_e5m2_to_fp64(i) for i in range(256)]


def e5m2_(value: float):
    """Create an E5M2 (8-bit float) expression."""
    from ..expr import Expr
    return Expr("e5m2", value=_encode_e5m2(value))
