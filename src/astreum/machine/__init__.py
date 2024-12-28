import threading
from typing import Callable, Dict, List, Optional, Tuple
import uuid

from src.astreum.machine.environment import Environment
from src.astreum.machine.expression import Expr
from src.astreum.machine.tokenizer import tokenize
from src.astreum.machine.parser import parse

class AstreumMachine:
    def __init__(self):
        # Initialize the global environment
        self.global_env = Environment()
        
        # Dictionary to manage user sessions: session_id -> local Environment
        self.sessions: Dict[str, Environment] = {}
        
        # Lock for thread-safe access to the global environment and sessions
        self.lock = threading.Lock()
    
    def create_session(self) -> str:
        """
        Create a new user session with a unique session ID and a fresh local environment.
        Returns the session ID.
        """
        session_id = str(uuid.uuid4())
        with self.lock:
            self.sessions[session_id] = Environment(parent=self.global_env)
        return session_id
    
    def terminate_session(self, session_id: str) -> bool:
        """
        Terminate an existing user session.
        Returns True if the session was successfully terminated, False otherwise.
        """
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            else:
                return False
    
    def get_session_env(self, session_id: str) -> Optional[Environment]:
        """
        Retrieve the local environment for a given session ID.
        Returns the Environment if found, None otherwise.
        """
        with self.lock:
            return self.sessions.get(session_id, None)
    
    def evaluate_code(self, code: str, session_id: str) -> Tuple[Optional[Expr], Optional[str]]:
        """
        Evaluate code within the context of a user's session.
        Returns a tuple of (Result Expression, Error Message).
        If evaluation is successful, Error Message is None.
        If an error occurs, Result Expression is None.
        """
        env = self.get_session_env(session_id)
        if env is None:
            return None, f"Session ID {session_id} not found."
        
        try:
            tkns = tokenize(input=code)
            expr, _ = parse(tokens=tkns)
            result = self.evaluate(expr, env)
            return result, None
        except Exception as e:
            return None, str(e)
    
    def evaluate(self, expr: Expr, env: Environment) -> Expr:

        if isinstance(expr, Expr.Integer):
            return expr
        elif isinstance(expr, Expr.String):
            return expr
        elif isinstance(expr, Expr.Symbol):
            value = env.get(expr.value)
            if value is not None:
                return value
            else:
                # Return the symbol itself if not found in the environment
                return expr
        elif isinstance(expr, Expr.ListExpr):
            if not expr.elements:
                raise ValueError("Empty list cannot be evaluated")
            
            first = expr.elements[0]
            if isinstance(first, Expr.Symbol):
                # Check if it's a user-defined function
                user_def_fn = env.get(first.value)
                if isinstance(user_def_fn, Expr.Function):
                    fn_params, fn_body = user_def_fn.params, user_def_fn.body
                    args = expr.elements[1:]
                    
                    if len(fn_params) != len(args):
                        raise TypeError(f"expected {len(fn_params)} arguments, got {len(args)}")
                    
                    # Create a new environment for the function execution, inheriting from the function's defining environment
                    new_env = Environment(parent=env)
                    
                    # Evaluate and bind each argument
                    for param, arg in zip(fn_params, args):
                        evaluated_arg = self.evaluate(arg, env)
                        new_env.set(param, evaluated_arg)
                    
                    # Evaluate the function body within the new environment
                    return self.evaluate(fn_body, new_env)
                
                # Check for special functions
                elif first.value in ["def", "+"]:
                    args = expr.elements[1:]

                    match first.value:
                        case "def":
                            if len(args) != 2:
                                raise TypeError("def expects exactly two arguments: a symbol and an expression")
                            if not isinstance(args[0], Expr.Symbol):
                                raise TypeError("First argument to def must be a symbol")
                            
                            var_name = args[0].value
                            var_value = self.evaluate(args[1], env)
                            env.set(var_name, var_value)
                            return args[0]  # Return the symbol name
                        
                        case "+":
                            # Ensure all arguments are integers
                            evaluated_args = [self.evaluate(arg, env) for arg in args]
                            if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                                raise TypeError("All arguments to + must be integers")
                            
                            # Sum the integer values and return as an Expr.Integer
                            result = sum(arg.value for arg in evaluated_args)
                            return Expr.Integer(result)

                else:
                    # Attempt to evaluate as a function application
                    func = self.evaluate(first, env)
                    if isinstance(func, Expr.Function):
                        fn_params, fn_body = func.params, func.body
                        args = expr.elements[1:]
                        
                        if len(fn_params) != len(args):
                            raise TypeError(f"expected {len(fn_params)} arguments, got {len(args)}")
                        
                        # Create a new environment for the function execution, inheriting from the function's defining environment
                        new_env = Environment(parent=func.env)
                        
                        # Evaluate and bind each argument
                        for param, arg in zip(fn_params, args):
                            evaluated_arg = self.evaluate(arg, env)
                            new_env.set(param, evaluated_arg)
                        
                        # Evaluate the function body within the new environment
                        return self.evaluate(fn_body, new_env)
                    else:
                        raise TypeError(f"'{first.value}' is not a function")
            else:
                evaluated_elements = [self.evaluate(e, env) for e in expr.elements]
                return Expr.ListExpr(evaluated_elements)
        elif isinstance(expr, Expr.Function):
            return expr
        else:
            raise TypeError(f"Unknown expression type: {type(expr)}")
