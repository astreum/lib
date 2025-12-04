"""High level eval helper that reuses the existing tokenizer, parser and evaluator."""

from __future__ import annotations

import uuid
from typing import Optional

from ..models.expression import Expr, error_expr
from ..parser import ParseError, parse
from ..tokenizer import tokenize


def script_eval(self, source: str, env_id: Optional[uuid.UUID] = None, meter=None) -> Expr:
    """Evaluate textual expressions by tokenizing, parsing and forwarding to high_eval."""
    tokens = tokenize(source)
    if not tokens:
        return error_expr("eval", "no expression provided")

    try:
        expr, rest = parse(tokens)
    except ParseError as exc:
        return error_expr("eval", f"parse error: {exc}")

    if rest:
        return error_expr("eval", "unexpected tokens after expression")

    return self.high_eval(expr=expr, env_id=env_id, meter=meter)
