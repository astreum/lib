from typing import List

from astreum.machine.models.expression import Expr
from astreum.machine.models.op_error import OpError
from astreum.machine.tokenizer import tokenize
from astreum.machine.parser import parse, ParseError


def handle_stack_parse(machine, stack: List[Expr]) -> None:
    if not stack:
        raise OpError("stack underflow")
    val = stack.pop()
    if val._tag != "str":
        raise OpError("parse requires a string")
    machine.meter.charge_bytes(len(val.value))
    tokens = tokenize(val.value)
    if not tokens:
        raise ParseError("no expressions in input")
    expr, _ = parse(tokens)
    stack.append(expr)
