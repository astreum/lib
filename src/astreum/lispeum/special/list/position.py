from astreum.lispeum.expression import Expr
from astreum.machine.environment import Environment


def handle_list_position(machine, list: Expr.ListExpr, predicate: Expr.Function, env: Environment) -> Expr:
    if not isinstance(list, Expr.ListExpr):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("First argument must be a list")
        ])
    
    if not isinstance(predicate, Expr.Function):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("Second argument must be a function")
        ])
    
    for idx, elem in enumerate(list.elements):
        new_env = Environment(parent=env)
        new_env.set(predicate.params[0], elem)
        
        result, _ = machine.evaluate_expression(predicate, new_env)

        if result == Expr.Boolean(True):
            return Expr.ListExpr([
                Expr.Integer(idx),
                Expr.ListExpr([])
            ])
    
    return Expr.ListExpr([
        Expr.ListExpr([]),
        Expr.ListExpr([])
    ])
