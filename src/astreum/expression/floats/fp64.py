def fp64_(value: float):
    """Create an FP64 (64-bit float) expression."""
    from astreum.expression.expr import Expr, FP64_SYMBOL
    return Expr("link", value=value, tail=FP64_SYMBOL)
