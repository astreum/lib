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


def run_iteration_step(
    machine: "Machine",
    fn: Expr,
    env,
    pre_stack: List[Expr],
) -> Expr:
    """Evaluate an iteration step and return its top result.

    Two closure forms are accepted (dispatch on ``fn._tag``):

    - ``"link"`` — quoted body. The body is treated as a list runtime
      program reached with no name bindings; the caller pre-pushes the
      iteration item(s) onto an isolated stack and the body reduces on
      top of them. The evaluator's list semantics are concatenative
      (``evaluator.py``), so ``\\'(1 +)`` works as "push 1, + pops 1+item".
    - ``"closure"`` — stored ``lambda`` closure. Pops the closure, builds
      ``Env(data={single_param: item}, parent=captured)`` exactly like
      ``apply`` does, and re-enters evaluation on a fresh stack with
      the single argument bound. Exactly one parameter is required.

    Any other tag is a hard type error matching the ``apply`` phrasing
    convention.

    Args:
        machine: The machine instance used to evaluate the body.
        fn: The closure argument popped from the caller's stack.
        env: The active environment (used for the quoted-body form).
        pre_stack: Isolated stack with one (``map``/``filter``/``each``/
            ``find``) or two (``fold``: ``[acc, item]``, item on top) values
            pre-pushed by the caller.

    Returns:
        The top of the result stack after evaluating the body.

    Raises:
        OpError: For unknown closure tags, multi-param closures, or an
            empty result stack (body yielded nothing).
    """
    if fn._tag == "link":
        cost = sum(e.size() for e in pre_stack)
        machine.meter.charge_bytes(cost + 1)
        result_stack = _evaluation(machine, fn, list(pre_stack), env)
        if not result_stack:
            return NIL
        return result_stack.pop()

    if fn._tag == "closure":
        c = fn._value
        if len(c.params) != 1:
            raise OpError(
                f"iteration closure takes 1 argument, got {len(c.params)}"
            )
        if not pre_stack:
            raise OpError("iteration closure missing argument")
        item = pre_stack[-1]
        cost = item.size()
        machine.meter.charge_bytes(cost)
        captured = machine.library[c.captured_env_uuid]
        apply_env = Env(data={c.params[0]: item}, parent=captured)
        apply_stack = []
        result_stack = _evaluation(machine, c.body, apply_stack, apply_env)
        if not result_stack:
            return NIL
        return result_stack.pop()

    raise OpError(f"fn of {fn._tag}")
