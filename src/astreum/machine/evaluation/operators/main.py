from typing import List

from astreum.machine.models.expression import Expr

from astreum.machine.evaluation.operators._def import handle_stack_def
from astreum.machine.evaluation.operators._fn import handle_stack_fn
from astreum.machine.evaluation.operators._lambda import handle_stack_lambda
from astreum.machine.evaluation.operators._if import handle_stack_if
from astreum.machine.evaluation.operators.actors.receive import handle_stack_receive
from astreum.machine.evaluation.operators.actors.send import handle_stack_send
from astreum.machine.evaluation.operators.actors.spawn import handle_stack_spawn
from astreum.machine.evaluation.operators.bitwise._and import handle_stack_and
from astreum.machine.evaluation.operators.bitwise._not import handle_stack_not
from astreum.machine.evaluation.operators.bitwise._or import handle_stack_or
from astreum.machine.evaluation.operators.bitwise.xor import handle_stack_xor
from astreum.machine.evaluation.operators.expression.head import handle_stack_head
from astreum.machine.evaluation.operators.expression.is_atom import handle_stack_is_atom
from astreum.machine.evaluation.operators.expression.is_eq import handle_stack_is_eq
from astreum.machine.evaluation.operators.expression.link import handle_stack_link
from astreum.machine.evaluation.operators.expression.tail import handle_stack_tail
from astreum.machine.evaluation.operators.floating.add import handle_stack_fadd
from astreum.machine.evaluation.operators.floating.div import handle_stack_fdiv
from astreum.machine.evaluation.operators.floating.mul import handle_stack_fmul
from astreum.machine.evaluation.operators.floating.sqrt import handle_stack_fsqrt
from astreum.machine.evaluation.operators.floating.sub import handle_stack_fsub
from astreum.machine.evaluation.operators.integer.add import handle_stack_add
from astreum.machine.evaluation.operators.integer.div import handle_stack_div
from astreum.machine.evaluation.operators.integer.mod import handle_stack_mod
from astreum.machine.evaluation.operators.integer.mul import handle_stack_mul
from astreum.machine.evaluation.operators.integer.sub import handle_stack_sub
from astreum.machine.evaluation.operators.shifts.rol import handle_stack_rol
from astreum.machine.evaluation.operators.shifts.ror import handle_stack_ror
from astreum.machine.evaluation.operators.shifts.sar import handle_stack_sar
from astreum.machine.evaluation.operators.shifts.shl import handle_stack_shl
from astreum.machine.evaluation.operators.shifts.shr import handle_stack_shr


OPERATOR_LIST = ["+", "add", "-", "sub", "*", "mul", "/", "div", "%", "mod", "&", "and", "|", "or", "^", "xor", "<<", ">>>", ">>", "rol", "ror", "fadd", "fsub", "fmul", "fdiv", "fsqrt", "~", "not", "fn", "lambda", "if", "def", "link", "head", "tail", "is_atom", "is_eq", "spawn", "send", "receive"]


def apply_operator(machine, symbol: Expr.Symbol, stack: List[Expr], env) -> List[Expr]:
    if symbol.value in ("+", "add"):
        handle_stack_add(machine, stack)

    elif symbol.value in ("-", "sub"):
        handle_stack_sub(machine, stack)

    elif symbol.value in ("*", "mul"):
        handle_stack_mul(machine, stack)

    elif symbol.value in ("/", "div"):
        handle_stack_div(machine, stack)

    elif symbol.value in ("%", "mod"):
        handle_stack_mod(machine, stack)

    elif symbol.value in ("&", "and"):
        handle_stack_and(machine, stack)

    elif symbol.value in ("|", "or"):
        handle_stack_or(machine, stack)

    elif symbol.value in ("^", "xor"):
        handle_stack_xor(machine, stack)

    elif symbol.value == "<<":
        handle_stack_shl(machine, stack)

    elif symbol.value == ">>>":
        handle_stack_shr(machine, stack)

    elif symbol.value == ">>":
        handle_stack_sar(machine, stack)

    elif symbol.value == "rol":
        handle_stack_rol(machine, stack)

    elif symbol.value == "ror":
        handle_stack_ror(machine, stack)

    elif symbol.value == "fadd":
        handle_stack_fadd(machine, stack)

    elif symbol.value == "fsub":
        handle_stack_fsub(machine, stack)

    elif symbol.value == "fmul":
        handle_stack_fmul(machine, stack)

    elif symbol.value == "fdiv":
        handle_stack_fdiv(machine, stack)

    elif symbol.value == "fsqrt":
        handle_stack_fsqrt(machine, stack)

    elif symbol.value in ("~", "not"):
        handle_stack_not(machine, stack)

    elif symbol.value == "fn":
        handle_stack_fn(machine, stack, env)

    elif symbol.value == "lambda":
        handle_stack_lambda(machine, stack, env)

    elif symbol.value == "if":
        return handle_stack_if(machine, stack, env)

    elif symbol.value == "def":
        handle_stack_def(machine, stack, env)

    elif symbol.value == "link":
        handle_stack_link(machine, stack)

    elif symbol.value == "head":
        handle_stack_head(machine, stack)

    elif symbol.value == "tail":
        handle_stack_tail(machine, stack)

    elif symbol.value == "is_atom":
        handle_stack_is_atom(machine, stack)

    elif symbol.value == "is_eq":
        handle_stack_is_eq(machine, stack)

    elif symbol.value == "spawn":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_spawn(machine, stack, env)

    elif symbol.value == "send":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_send(machine, stack)

    elif symbol.value == "receive":
        if not machine.allow_threading:
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_receive(machine, stack)

    return stack
