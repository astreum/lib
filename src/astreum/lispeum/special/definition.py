from astreum.lispeum.expression import Expr
from astreum.machine.environment import Environment


def handle_definition(machine, args: Expr.ListExpr, env: Environment) -> Expr:
        if len(args) != 2:
            return Expr.Error(
                category="SyntaxError",
                message="def expects exactly two arguments: a symbol and an expression"
            )
        
        if not isinstance(args[0], Expr.Symbol):
            return Expr.Error(
                category="TypeError",
                message="First argument to def must be a symbol"
            )
    
        var_name = args[0].value

        result = machine.evaluate_expression(args[1], env)

        if isinstance(result, Expr.Error):
            return result

        env.set(var_name, result)
    
        return result
