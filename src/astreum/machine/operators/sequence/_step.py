import uuid
from typing import TYPE_CHECKING, Callable, List

from astreum.expression import Expr, NIL, get_expr_tag
from astreum.machine import OpError
from astreum.machine.environment import Env
from astreum.machine.operators._tags import FUNCTION_TAGS

if TYPE_CHECKING:
    from astreum.machine.main import Machine


def _evaluation(machine, expr, stack, env):
    """Lazy import to break circular dependency."""
    from astreum.machine.evaluator import evaluation
    return evaluation(machine, expr, stack, env)


def _step_tagged(machine: "Machine", fn: Expr, env, pre_stack: List[Expr]) -> Expr:
    """Evaluate one iteration of a (dyn|pure|lex) function.

    Binds the single declared parameter to ``pre_stack[-1]`` and evaluates the
    body on a fresh empty stack. No tag dispatch happens here — the caller has
    already classified ``fn`` as a tagged function.
    """
    inner = fn._head
    body = inner._head
    params = inner._tail
    tag = fn._tail.value

    if tag == "lex":
        env_uuid_bytes = body._head._value
        body = body._tail
        parent = machine.library[uuid.UUID(bytes=env_uuid_bytes)]
    elif tag == "dyn":
        parent = env
    elif tag == "pure":
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
    machine.meter.charge_bytes(item.size())

    apply_env = Env(data={param_names[0]: item}, parent=parent)
    result_stack = _evaluation(machine, body, [], apply_env)
    if not result_stack:
        return NIL
    return result_stack.pop()


def _step_bare(machine: "Machine", fn: Expr, env, pre_stack: List[Expr]) -> Expr:
    """Evaluate one iteration of a bare link (quotation).

    The body is evaluated on a copy of ``pre_stack``; no parameter binding.
    No tag dispatch happens here — the caller has already classified ``fn`` as
    a bare link.
    """
    cost = sum(e.size() for e in pre_stack)
    machine.meter.charge_bytes(cost + 1)
    result_stack = _evaluation(machine, fn, list(pre_stack), env)
    if not result_stack:
        return NIL
    return result_stack.pop()


def pick_step(fn: Expr) -> Callable:
    """Classify ``fn`` once and return the specialized step function.

    Raises ``OpError`` if ``fn`` is neither a tagged function nor a bare link.
    """
    fn_tag = get_expr_tag(fn)
    if fn_tag in FUNCTION_TAGS:
        return _step_tagged
    if fn_tag == "link":
        return _step_bare
    raise OpError(f"fn of {fn_tag}")