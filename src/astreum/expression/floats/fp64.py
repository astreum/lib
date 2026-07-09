def fp64_(value: float):
    """Create an FP64 (64-bit float) expression."""
    from astreum.expression.expr import Expr
    return Expr("fp64", value=value)
