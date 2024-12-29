import threading
from typing import Callable, Dict, List, Optional, Tuple
import uuid

from astreum.machine.environment import Environment
from astreum.machine.expression import Expr
from astreum.machine.tokenizer import tokenize
from astreum.machine.parser import parse

class AstreumMachine:
    def __init__(self):
        self.global_env = Environment()
        
        self.sessions: Dict[str, Environment] = {}
        
        self.lock = threading.Lock()
    
    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        with self.lock:
            self.sessions[session_id] = Environment(parent=self.global_env)
        return session_id
    
    def terminate_session(self, session_id: str) -> bool:
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            else:
                return False
    
    def get_session_env(self, session_id: str) -> Optional[Environment]:
        with self.lock:
            return self.sessions.get(session_id, None)
    
    def evaluate_code(self, code: str, session_id: str) -> Tuple[Optional[Expr], Optional[str]]:
        session_env = self.get_session_env(session_id)
        if session_env is None:
            return None, f"Session ID {session_id} not found."
        
        try:
            tkns = tokenize(input=code)
            expr, _ = parse(tokens=tkns)
            result = self.evaluate_expression(expr, session_env)
            return result, None
        except Exception as e:
            return None, str(e)
    
    def evaluate_expression(self, expr: Expr, env: Environment) -> Expr:
        if isinstance(expr, Expr.Integer):
            return expr
        
        elif isinstance(expr, Expr.String):
            return expr
        
        elif isinstance(expr, Expr.Symbol):
            value = env.get(expr.value)
            if value is not None:
                return value
            else:
                raise ValueError("Variable not found in environments.")
        
        elif isinstance(expr, Expr.ListExpr):
            if not expr.elements:
                raise ValueError("Empty list cannot be evaluated.")
            
            first = expr.elements[0]

            if isinstance(first, Expr.Symbol):
                
                first_symbol_value = env.get(first.value)

                if first_symbol_value and not isinstance(first_symbol_value, Expr.Function):
                    evaluated_elements = [self.evaluate_expression(e, env) for e in expr.elements]
                    return Expr.ListExpr(evaluated_elements) 
                    args = expr.elements[1:]
                    
                    if len(fn_params) != len(args):
                        raise ValueError(f"Expected {len(fn_params)} arguments, got {len(args)}.")
                    
                    # Create a new environment for the function execution, inheriting from the function's defining environment
                    new_env = Environment(parent=env)
                    
                    # Evaluate and bind each argument
                    for param, arg in zip(fn_params, args):
                        evaluated_arg = self.evaluate_expression(arg, env)
                        new_env.set(param, evaluated_arg)
                    
                    # Evaluate the function body within the new environment
                    return self.evaluate_expression(fn_body, new_env)
                
                elif first.value in ["def", "+"]:
                    args = expr.elements[1:]

                    match first.value:
                        case "def":
                            if len(args) != 2:
                                raise ValueError("def expects exactly two arguments: a symbol and an expression")
                            if not isinstance(args[0], Expr.Symbol):
                                raise ValueError("First argument to def must be a symbol")
                            
                            var_name = args[0].value
                            var_value = self.evaluate_expression(args[1], env)
                            env.set(var_name, var_value)
                            return args[0]
                        
                        case "+":
                            evaluated_args = [self.evaluate_expression(arg, env) for arg in args]
                            if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                                raise ValueError("All arguments to + must be integers")
                            
                            result = sum(arg.value for arg in evaluated_args)
                            return Expr.Integer(result)

            else:
                evaluated_elements = [self.evaluate_expression(e, env) for e in expr.elements]
                return Expr.ListExpr(evaluated_elements)
        elif isinstance(expr, Expr.Function):
            return expr
        else:
            raise ValueError(f"Unknown expression type: {type(expr)}")
