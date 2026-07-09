from typing import List

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError
from astreum.machine.tokenizer import tokenize
from astreum.machine.parser import parse, ParseError


def handle_stack_parse(machine, stack: List[Expr], env) -> None:
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


def handle_stack_parse_with_result(machine, stack, env):
    try:
        handle_stack_parse(machine, stack, env)
        result = stack.pop()
        stack.append(link(result, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
