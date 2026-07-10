import uuid
from typing import TYPE_CHECKING, List

from astreum.expression import Expr, NIL, link
from astreum.machine import OpError
from astreum.machine.environment import Env

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluator import evaluation
    return evaluation(machine, expr, stack, env)


FUNCTION_TAGS = frozenset({"fn", "box", "lambda"})


def _is_tagged_function(fn: Expr) -> bool:
    return (
        fn._tag == "link"
        and fn._tail is not None
        and fn._tail._tag == "symbol"
        and fn._tail.value in FUNCTION_TAGS
    )


def run_iteration_step(
    machine: "Machine",
    fn: Expr,
    env,
    pre_stack: List[Expr],
) -> Expr:
    """Evaluate an iteration step and return its top result.

    Two forms are accepted:

    - Tagged function value ``((body . params) . 'fn|'box|'lambda)`` —
      extracts the single parameter, builds ``Env(data={param: item},
      parent=parent_env)``, and evals the body. Exactly one parameter
      is required.

    - Quoted body (bare link) — the body is treated as a list runtime
      program reached with no name bindings; the caller pre-pushes the
      iteration item(s) onto an isolated stack and the body reduces on
      top of them. The evaluator's list semantics are concatenative
      (``evaluator.py``), so ``\\'(1 +)`` works as "push 1, + pops 1+item".

    Any other tag is a hard type error matching the ``apply`` phrasing
    convention.
    """
    if _is_tagged_function(fn):
        inner = fn._head
        body = inner._head
        params = inner._tail
        tag = fn._tail.value

        if tag == "lambda":
            env_uuid_bytes = body._head._value
            body = body._tail
            parent = machine.library[uuid.UUID(bytes=env_uuid_bytes)]
        elif tag == "fn":
            parent = env
        elif tag == "box":
            parent = None

        param_names = []
        p = params
        while p is not None and p._tag == "link" and p._head is not None:
            if p._head._tag != "symbol":
                raise OpError(
                    f"iteration fn has non-symbol param {p._head._tag}"
                )
            param_names.append(p._head.value)
            p = p._tail

        if len(param_names) != 1:
            raise OpError(
                f"iteration fn takes 1 argument, got {len(param_names)}"
            )

        if not pre_stack:
            raise OpError("iteration fn missing argument")
        item = pre_stack[-1]
        cost = item.size()
        machine.meter.charge_bytes(cost)

        apply_env = Env(data={param_names[0]: item}, parent=parent)
        apply_stack = []
        result_stack = _evaluation(machine, body, apply_stack, apply_env)
        if not result_stack:
            return NIL
        return result_stack.pop()

    if fn._tag == "link":
        cost = sum(e.size() for e in pre_stack)
        machine.meter.charge_bytes(cost + 1)
        result_stack = _evaluation(machine, fn, list(pre_stack), env)
        if not result_stack:
            return NIL
        return result_stack.pop()

    raise OpError(f"fn of {fn._tag}")
