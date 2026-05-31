from typing import List

from src.astreum.machine.models.environment import Env
from src.astreum.machine.models.expression import Expr
from src.astreum.machine.main import Machine
from src.astreum.machine.evaluation.main import evaluation


def is_truthy(expr: Expr) -> bool:
    if isinstance(expr, Expr.Bytes):
        return int.from_bytes(expr.value, "big") != 0
    if isinstance(expr, Expr.Link):
        return expr.head is not None


def handle_stack_if(
    machine: "Machine", stack: List[Expr], env: Env
) -> List[Expr]:
    else_branch = stack.pop()
    then_branch = stack.pop()
    condition = stack.pop()
    machine.meter.charge_bytes(condition.size())
    branch = then_branch if is_truthy(condition) else else_branch
    return evaluation(machine, branch, stack, env)
