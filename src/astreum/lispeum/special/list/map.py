from astreum.lispeum.expression import Expr
from astreum.machine.environment import Environment


def handle_list_map(machine, list: Expr.ListExpr, func: Expr.Function, env: Environment) -> Expr:
    if not isinstance(list, Expr.ListExpr):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("First argument must be a list")
        ])
    
    if not isinstance(func, Expr.Function):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("Second argument must be a function")
        ])
    
    mapped_elements = []
    for elem in list.elements:
        new_env = Environment(parent=env)
        new_env.set(func.params[0], elem)
        
        mapped_elem = machine.evaluate_expression(func.body, new_env)
        
        mapped_elements.append(mapped_elem)
    
    return Expr.ListExpr([
        Expr.ListExpr(mapped_elements),
        Expr.ListExpr([])
    ])
