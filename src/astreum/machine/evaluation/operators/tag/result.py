from typing import List

from astreum.machine.models.expression import Expr, link, symbol, str_


def _evaluation(machine, expr, stack, env):
    from astreum.machine.evaluation.main import evaluation
    return evaluation(machine, expr, stack, env)


def _is_tagged(item):
    return item._tag == "link" and item._tail is not None and item._tail._tag == "symbol"


def handle_stack_result(
    machine, stack: List[Expr], env
) -> List[Expr]:
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
