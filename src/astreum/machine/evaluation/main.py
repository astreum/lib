from typing import List, Optional, Tuple

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.meter import MeterExceededError
from astreum.machine.models.op_error import OpError
from astreum.machine.evaluation.operators.main import OPERATOR_LIST, apply_operator

STACK_VOID_OPS = {"drop", "dup", "swap", "rot", "dip"}


def _resolve_op(name: str) -> Tuple[Optional[str], bool]:
    """Resolve a symbol name for dispatch.
    Returns (stem, tagged_results_flag):
      (name, False)   -> bare operator, run via apply_operator
      (stem, True)    -> <primitive>? form, run via _tag_results
      (None, False)   -> not an operator (unbound)."""
    if name in OPERATOR_LIST:
        return (name, False)
    if name.endswith("?") and name[:-1] in OPERATOR_LIST:
        return (name[:-1], True)
    return (None, False)


def _tag_results(machine, stem: str, stack: List[Expr], env: Env) -> List[Expr]:
    try:
        stack = apply_operator(machine, Expr.Symbol(stem), stack, env)
    except MeterExceededError:
        raise
    except IndexError:
        machine.meter.charge_bytes(1)
        stack.append(Expr.Link(Expr.Symbol("err"), Expr.String("stack underflow")))
        return stack
    except OpError as exc:
        machine.meter.charge_bytes(1)
        stack.append(Expr.Link(Expr.Symbol("err"), Expr.String(str(exc))))
        return stack
    except Exception as exc:
        machine.meter.charge_bytes(1)
        stack.append(Expr.Link(Expr.Symbol("err"), Expr.String(str(exc) or type(exc).__name__)))
        return stack

    if stem in STACK_VOID_OPS:
        stack.append(NIL)

    if not stack:
        machine.meter.charge_bytes(1)
        stack.append(Expr.Link(Expr.Symbol("ok"), NIL))
        return stack

    machine.meter.charge_bytes(1)
    stack[-1] = Expr.Link(Expr.Symbol("ok"), stack[-1])
    return stack


def evaluation(machine, expr: Expr, stack: List[Expr] = [], env: Env = Env()) -> List[Expr]:

    # ATOM: Symbol
    if isinstance(expr, Expr.Symbol):
        stem, tagged_results_flag = _resolve_op(expr.value)

        if machine.mode == "deterministic":
            # ? is a no-op in deterministic mode: strip suffix, run bare.
            # No tagged tuples on the stack -> consensus reproducibility preserved.
            if tagged_results_flag:
                tagged_results_flag = False
            if stem is not None:
                try:
                    stack = apply_operator(machine, Expr.Symbol(stem), stack, env)
                except OpError:
                    machine.meter.charge_bytes(1)
                    stack.append(NIL)
            else:
                bound = env.get(expr.value)
                if bound is None:
                    machine.meter.charge_bytes(expr.size() + 1)
                    stack.append(Expr.Link(None, None))
                else:
                    machine.meter.charge_bytes(expr.size() + bound.size())
                    stack.append(bound)
        else:
            bound = env.get(expr.value)
            if bound is not None:
                machine.meter.charge_bytes(expr.size() + bound.size())
                stack.append(bound)
            elif stem is not None:
                if stem in ("fn", "lambda") and tagged_results_flag:
                    try:
                        stack = apply_operator(machine, Expr.Symbol(stem), stack, env)
                    except OpError as exc:
                        machine.meter.charge_bytes(1)
                        stack.append(Expr.Link(Expr.Symbol("err"), Expr.String(str(exc))))
                        return stack
                    result = stack[-1]
                    if (
                        isinstance(result, Expr.Link)
                        and isinstance(result.head, Expr.Symbol)
                        and result.head.value in ("ok", "err")
                    ):
                        return stack
                    machine.meter.charge_bytes(1)
                    stack[-1] = Expr.Link(Expr.Symbol("ok"), result)
                    return stack
                if tagged_results_flag:
                    stack = _tag_results(machine, stem, stack, env)
                else:
                    try:
                        stack = apply_operator(machine, Expr.Symbol(stem), stack, env)
                    except OpError:
                        machine.meter.charge_bytes(1)
                        stack.append(NIL)
            else:
                machine.meter.charge_bytes(expr.size() + 1)
                stack.append(Expr.Link(None, None))
        return stack

    # ATOM: Bytes / Int / Float / String
    if isinstance(expr, (Expr.Bytes, Expr.Int, Expr.Float, Expr.String)):
        machine.meter.charge_bytes(expr.size())
        stack.append(expr)
        return stack

    # LINK: Pair of Atoms
    if isinstance(expr, Expr.Link):
        # If the list starts with 'quote', treat as quotation
        if (isinstance(expr.head, Expr.Symbol) and expr.head.value == "'"):
            if expr.tail is None:
                # (quote) with no argument – push nil
                machine.meter.charge_bytes(1)
                stack.append(NIL)
            else:
                # push the tail expression itself, unevaluated
                machine.meter.charge_bytes(expr.tail.size())
                stack.append(expr.tail)
            return stack
        if expr.head is not None:
            stack = evaluation(machine, expr.head, stack, env)
        if expr.tail is not None:
            stack = evaluation(machine, expr.tail, stack, env)
        return stack
