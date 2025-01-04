from astreum.lispeum.expression import Expr
from astreum.machine.environment import Environment


def handle_list_fold(machine, list: Expr.ListExpr, initial: Expr, func: Expr.Function, env: Environment) -> Expr:
    if not isinstance(list, Expr.ListExpr):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("First argument must be a list")
        ])
    
    if not isinstance(func, Expr.Function):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("Third argument must be a function")
        ])
    
    result = initial
    for elem in list.elements:
        new_env = Environment(parent=env)
        new_env.set(func.params[0], result)
        new_env.set(func.params[1], elem)
        
        result = machine.evaluate_expression(func, new_env)
    
    return Expr.ListExpr([
        result,
        Expr.ListExpr([])
    ])
