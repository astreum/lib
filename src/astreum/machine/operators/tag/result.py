from typing import List

from astreum.expression import Expr, link, symbol, str_


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluator import evaluation
    return evaluation(machine, expr, stack, env)


def _is_tagged(item):
    return item._tag == "link" and item._tail is not None and item._tail._tag == "symbol"


def handle_stack_result(
    machine, stack: List[Expr], env
) -> List[Expr]:
    """Process a tagged result value on the stack, handling errors and continuations.

    If the top of the stack is an ``err``-tagged value, leaves it on the stack.
    If it is another tagged value (non-``err``), extracts the head. Otherwise,
    treats the top as a continuation and processes the next stack item.

    When a continuation and a non-``err``-tagged value are present, extracts the
    tagged value's head and evaluates the continuation. Error cases push
    ``err``-tagged values onto the stack.

    Args:
        machine: The machine instance used to continue evaluation.
        stack: The current evaluation stack; modified in place.
        env: The environment in which continuations are evaluated.

    Returns:
        The updated stack after processing. Either contains an ``err``-tagged
        value, an extracted value, or the result of evaluating a continuation.

    Note:
        Stack underflow and incorrect types produce ``err``-tagged values
        directly on the stack (no exceptions raised).
    """
    if not stack:
        stack.append(link(str_("stack underflow"), symbol("err")))
        return stack

    top = stack.pop()

    if _is_tagged(top):
        if top._tail.value == "err":
            stack.append(top)
        else:
            stack.append(top._head)
        return stack

    continuation = top

    if not stack:
        stack.append(continuation)
        stack.append(link(str_("no tagged value on stack"), symbol("err")))
        return stack

    tagged = stack.pop()

    if not _is_tagged(tagged):
        stack.append(tagged)
        stack.append(continuation)
        stack.append(link(str_("expected tagged value, got raw"), symbol("err")))
        return stack

    if tagged._tail.value == "err":
        stack.append(tagged)
        return stack

    stack.append(tagged._head)
    return _evaluation(machine, continuation, stack, env)
