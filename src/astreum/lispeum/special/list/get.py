

from astreum.lispeum.expression import Expr
from astreum.machine.environment import Environment


def handle_list_get(machine, list: Expr.ListExpr, index: Expr.Integer, env: Environment) -> Expr:
    if not isinstance(list, Expr.ListExpr):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("First argument must be a list")
        ])
    
    if index.value < 0 or index.value >= len(list.elements):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("Index out of bounds")
        ])
    
    return machine.evaluate_expression(list.elements[index])
