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
from astreum.machine.evaluation.operators.expression.eval import handle_stack_eval
from astreum.machine.evaluation.operators.expression.ref import handle_stack_ref
from astreum.machine.evaluation.operators.expression.load import handle_stack_load
from astreum.machine.evaluation.operators.expression.quote import handle_stack_quote
from astreum.machine.evaluation.operators.expression.symbol import handle_stack_symbol
from astreum.machine.evaluation.operators.stack.dip import handle_stack_dip
from astreum.machine.evaluation.operators.stack.drop import handle_stack_drop
from astreum.machine.evaluation.operators.stack.dup import handle_stack_dup
from astreum.machine.evaluation.operators.stack.swap import handle_stack_swap
from astreum.machine.evaluation.operators.arithmetic.sqrt import handle_stack_sqrt
from astreum.machine.evaluation.operators.arithmetic.add import handle_stack_add
from astreum.machine.evaluation.operators.arithmetic.sub import handle_stack_sub
from astreum.machine.evaluation.operators.arithmetic.mul import handle_stack_mul
from astreum.machine.evaluation.operators.arithmetic.div import handle_stack_div
from astreum.machine.evaluation.operators.arithmetic.mod import handle_stack_mod
from astreum.machine.evaluation.operators.shifts.rol import handle_stack_rol
from astreum.machine.evaluation.operators.shifts.ror import handle_stack_ror
from astreum.machine.evaluation.operators.shifts.sar import handle_stack_sar
from astreum.machine.evaluation.operators.shifts.shl import handle_stack_shl
from astreum.machine.evaluation.operators.shifts.shr import handle_stack_shr
from astreum.machine.evaluation.operators.string.str import handle_stack_str
from astreum.machine.evaluation.operators.float import handle_stack_float
from astreum.machine.evaluation.operators.int import handle_stack_int
from astreum.machine.evaluation.operators.bytes.main import handle_stack_bytes
from astreum.machine.evaluation.operators.bytes.concat import handle_stack_concat
from astreum.machine.evaluation.operators.bytes.split import handle_stack_split
from astreum.machine.evaluation.operators.bytes.size import handle_stack_size
from astreum.machine.evaluation.operators.bytes.index import handle_stack_index


OPERATOR_LIST = ["+", "-", "*", "/", "%", "&", "|", "^", "<<", ">>>", ">>", "rol", "ror", "sqrt", "~", "fn", "lambda", "if", "def", "link", "head", "tail", "is_atom", "is_eq", "drop", "dup", "swap", "dip", "spawn", "send", "receive", "eval", "ref", "load", "quote", "symbol", "str", "float", "int", "bytes", "concat", "split", "size", "index"]


def apply_operator(machine, symbol: Expr.Symbol, stack: List[Expr], env) -> List[Expr]:
    if symbol.value == "+":
        handle_stack_add(machine, stack)

    elif symbol.value == "-":
        handle_stack_sub(machine, stack)

    elif symbol.value == "*":
        handle_stack_mul(machine, stack)

    elif symbol.value == "/":
        handle_stack_div(machine, stack)

    elif symbol.value == "%":
        handle_stack_mod(machine, stack)

    elif symbol.value == "&":
        handle_stack_and(machine, stack)

    elif symbol.value == "|":
        handle_stack_or(machine, stack)

    elif symbol.value == "^":
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

    elif symbol.value == "sqrt":
        handle_stack_sqrt(machine, stack)

    elif symbol.value == "~":
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

    elif symbol.value == "eval":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_eval(machine, stack, env)

    elif symbol.value == "ref":
        handle_stack_ref(machine, stack)

    elif symbol.value == "load":
        handle_stack_load(machine, stack)

    elif symbol.value == "is_atom":
        handle_stack_is_atom(machine, stack)

    elif symbol.value == "is_eq":
        handle_stack_is_eq(machine, stack)

    elif symbol.value == "drop":
        handle_stack_drop(machine, stack)

    elif symbol.value == "dup":
        handle_stack_dup(machine, stack)

    elif symbol.value == "swap":
        handle_stack_swap(machine, stack)

    elif symbol.value == "dip":
        return handle_stack_dip(machine, stack, env)

    elif symbol.value == "spawn":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_spawn(machine, stack, env)

    elif symbol.value == "send":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_send(machine, stack)

    elif symbol.value == "receive":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(Expr.Link(None, None))
            return stack
        return handle_stack_receive(machine, stack)

    elif symbol.value == "quote":
        handle_stack_quote(machine, stack)

    elif symbol.value == "symbol":
        handle_stack_symbol(machine, stack)

    elif symbol.value == "str":
        handle_stack_str(machine, stack)

    elif symbol.value == "float":
        handle_stack_float(machine, stack)

    elif symbol.value == "int":
        handle_stack_int(machine, stack)

    elif symbol.value == "bytes":
        handle_stack_bytes(machine, stack)

    elif symbol.value == "concat":
        handle_stack_concat(machine, stack)

    elif symbol.value == "split":
        handle_stack_split(machine, stack)

    elif symbol.value == "size":
        handle_stack_size(machine, stack)

    elif symbol.value == "index":
        handle_stack_index(machine, stack)

    return stack
