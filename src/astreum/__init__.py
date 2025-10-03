"""Lightweight package initializer to avoid circular imports during tests.

Exports are intentionally minimal; import submodules directly as needed:
 - Node, Expr, Env, tokenize, parse -> from astreum._node or astreum.lispeum
 - Validation types -> from astreum._validation
 - Storage types -> from astreum._storage
"""

__all__: list[str] = []
