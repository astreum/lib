from typing import List

from src.astreum.machine.models.environment import Env
from src.astreum.machine.models.expression import Expr
from src.astreum.machine.main import Machine
from src.astreum.machine.evaluation.main import evaluation


def handle_stack_fn(
    machine: "Machine", stack: List[Expr], env: Env
) -> None:
    body = stack.pop()
    params = stack.pop()
    param_list = []
    p = params
    while isinstance(p, Expr.Link) and p.head is not None and isinstance(p, Expr.Link):
        param_list.append(p.head.value)
        p = p.tail
    num_args = len(param_list)
    args = []
    for _ in range(num_args):
        args.append(stack.pop())
    args.reverse()

    # Charge: param symbols + arg values (def-per-binding model)
    cost = params.size() + sum(a.size() for a in args)
    machine.meter.charge_bytes(cost)

    fn_env_data = dict(zip(param_list, args))
    fn_env = Env(data=fn_env_data, parent=env)
    fn_stack = []
    result_stack = evaluation(machine, body, fn_stack, fn_env)
    if result_stack:
        result = result_stack.pop()
        stack.append(result)
