import threading
from typing import Dict, Optional
import uuid

from astreum.lispeum.special.definition import handle_definition
from astreum.lispeum.special.list.all import handle_list_all
from astreum.lispeum.special.list.any import handle_list_any
from astreum.lispeum.special.list.fold import handle_list_fold
from astreum.lispeum.special.list.get import handle_list_get
from astreum.lispeum.special.list.insert import handle_list_insert
from astreum.lispeum.special.list.map import handle_list_map
from astreum.lispeum.special.list.position import handle_list_position
from astreum.lispeum.special.list.remove import handle_list_remove
from astreum.machine.environment import Environment
from astreum.lispeum.expression import Expr
from astreum.lispeum.tokenizer import tokenize
from astreum.lispeum.parser import parse

class AstreumMachine:
    def __init__(self, node: 'Node' = None):
        self.global_env = Environment(node=node)
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
    
    def evaluate_code(self, code: str, session_id: str) -> Expr:
        session_env = self.get_session_env(session_id)
        if session_env is None:
            raise ValueError(f"Session ID {session_id} not found.")
        
        try:
            tkns = tokenize(input=code)
            expr, _ = parse(tokens=tkns)
            result = self.evaluate_expression(expr, session_env)
            return result
        
        except Exception as e:
            raise ValueError(e)
    
    def evaluate_expression(self, expr: Expr, env: Environment) -> Expr:
        if isinstance(expr, Expr.Boolean) or isinstance(expr, Expr.Integer) or isinstance(expr, Expr.String) or isinstance(expr, Expr.Error):
            return expr
        
        elif isinstance(expr, Expr.Symbol):
            value = env.get(expr.value)
            
            if value:
                return value
            else:
                return Expr.Error(
                    category="NameError",
                    message=f"Variable '{expr.value}' not found in environments."
                )
        
        elif isinstance(expr, Expr.ListExpr):
            
            if len(expr.elements) == 0:
                return expr 
            
            if len(expr.elements) == 1:
                return self.evaluate_expression(expr=expr.elements[0], env=env)
            
            first = expr.elements[0]

            if isinstance(first, Expr.Symbol):
                
                first_symbol_value = env.get(first.value)

                if first_symbol_value and not isinstance(first_symbol_value, Expr.Function):
                    evaluated_elements = [self.evaluate_expression(e, env) for e in expr.elements]
                    return Expr.ListExpr(evaluated_elements)
                
                elif first.value == "def":
                    return handle_definition(
                        machine=self,
                        args=expr.elements[1:],
                        env=env
                    )

                # List
                elif first.value == "list.new":
                    return Expr.ListExpr([self.evaluate_expression(arg, env) for arg in expr.elements[1:]])

                elif first.value == "list.get":
                    args = expr.elements[1:]
                    if len(args) != 2:
                        return Expr.Error(
                            category="SyntaxError",
                            message="list.get expects exactly two arguments: a list and an index"
                        )
                    list_obj = self.evaluate_expression(args[0], env)
                    index = self.evaluate_expression(args[1], env)
                    return handle_list_get(self, list_obj, index, env)

                elif first.value == "list.insert":
                    args = expr.elements[1:]
                    if len(args) != 3:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.insert expects exactly three arguments: a list, an index, and a value")
                        ])
                    
                    return handle_list_insert(
                        list=self.evaluate_expression(args[0], env),
                        index=self.evaluate_expression(args[1], env),
                        value=self.evaluate_expression(args[2], env),
                    )

                elif first.value == "list.remove":
                    args = expr.elements[1:]
                    if len(args) != 2:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.remove expects exactly two arguments: a list and an index")
                        ])
                    
                    return handle_list_remove(
                        list=self.evaluate_expression(args[0], env),
                        index=self.evaluate_expression(args[1], env),
                    )

                elif first.value == "list.length":
                    args = expr.elements[1:]
                    if len(args) != 1:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.length expects exactly one argument: a list")
                        ])
                    
                    list_obj = self.evaluate_expression(args[0], env)
                    if not isinstance(list_obj, Expr.ListExpr):
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("Argument must be a list")
                        ])
                    
                    return Expr.ListExpr([
                        Expr.Integer(len(list_obj.elements)),
                        Expr.ListExpr([]) 
                    ])

                elif first.value == "list.fold":
                    if len(args) != 3:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.fold expects exactly three arguments: a list, an initial value, and a function")
                        ])
                    
                    return handle_list_fold(
                        machine=self,
                        list=self.evaluate_expression(args[0], env),
                        initial=self.evaluate_expression(args[1], env),
                        func=self.evaluate_expression(args[2], env),
                        env=env,
                    )

                elif first.value == "list.map":
                    if len(args) != 2:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.map expects exactly two arguments: a list and a function")
                        ])
                    
                    return handle_list_map(
                        machine=self,
                        list=self.evaluate_expression(args[0], env),
                        func=self.evaluate_expression(args[1], env),
                        env=env,
                    )

                elif first.value == "list.position":
                    if len(args) != 2:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.position expects exactly two arguments: a list and a function")
                        ])
                    
                    return handle_list_position(
                        machine=self,
                        list=self.evaluate_expression(args[0], env),
                        predicate=self.evaluate_expression(args[1], env),
                        env=env,
                    )

                elif first.value == "list.any":
                    if len(args) != 2:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.any expects exactly two arguments: a list and a function")
                        ])
                    
                    return handle_list_any(
                        machine=self,
                        list=self.evaluate_expression(args[0], env),
                        predicate=self.evaluate_expression(args[1], env),
                        env=env,
                    )

                elif first.value == "list.all":
                    if len(args) != 2:
                        return Expr.ListExpr([
                            Expr.ListExpr([]),
                            Expr.String("list.all expects exactly two arguments: a list and a function")
                        ])
                    
                    return handle_list_all(
                        machine=self,
                        list=self.evaluate_expression(args[0], env),
                        predicate=self.evaluate_expression(args[1], env),
                        env=env,
                    )

                # Number
                elif first.value == "+":
                    evaluated_args = [self.evaluate_expression(arg, env) for arg in expr.elements[1:]]

                    # Check for non-integer arguments
                    if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                        return Expr.Error(
                            category="TypeError",
                            message="All arguments to + must be integers"
                        )
                    
                    # Sum up the integer values
                    result = sum(arg.value for arg in evaluated_args)
                    return Expr.Integer(result)
                
                # Subtraction
                elif first.value == "-":
                    evaluated_args = [self.evaluate_expression(arg, env) for arg in expr.elements[1:]]

                    # Check for non-integer arguments
                    if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                        return Expr.Error(
                            category="TypeError",
                            message="All arguments to - must be integers"
                        )
                    
                    # With only one argument, negate it
                    if len(evaluated_args) == 1:
                        return Expr.Integer(-evaluated_args[0].value)
                    
                    # With multiple arguments, subtract all from the first
                    result = evaluated_args[0].value
                    for arg in evaluated_args[1:]:
                        result -= arg.value
                    
                    return Expr.Integer(result)
                
                # Multiplication
                elif first.value == "*":
                    evaluated_args = [self.evaluate_expression(arg, env) for arg in expr.elements[1:]]

                    # Check for non-integer arguments
                    if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                        return Expr.Error(
                            category="TypeError",
                            message="All arguments to * must be integers"
                        )
                    
                    # Multiply all values
                    result = 1
                    for arg in evaluated_args:
                        result *= arg.value
                    
                    return Expr.Integer(result)
                
                # Division (integer division)
                elif first.value == "/":
                    evaluated_args = [self.evaluate_expression(arg, env) for arg in expr.elements[1:]]

                    # Check for non-integer arguments
                    if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                        return Expr.Error(
                            category="TypeError",
                            message="All arguments to / must be integers"
                        )
                    
                    # Need exactly two arguments
                    if len(evaluated_args) != 2:
                        return Expr.Error(
                            category="ArgumentError",
                            message="The / operation requires exactly two arguments"
                        )
                    
                    dividend = evaluated_args[0].value
                    divisor = evaluated_args[1].value
                    
                    if divisor == 0:
                        return Expr.Error(
                            category="DivisionError",
                            message="Division by zero"
                        )
                    
                    return Expr.Integer(dividend // divisor)  # Integer division
                
                # Remainder (modulo)
                elif first.value == "%":
                    evaluated_args = [self.evaluate_expression(arg, env) for arg in expr.elements[1:]]

                    # Check for non-integer arguments
                    if not all(isinstance(arg, Expr.Integer) for arg in evaluated_args):
                        return Expr.Error(
                            category="TypeError",
                            message="All arguments to % must be integers"
                        )
                    
                    # Need exactly two arguments
                    if len(evaluated_args) != 2:
                        return Expr.Error(
                            category="ArgumentError",
                            message="The % operation requires exactly two arguments"
                        )
                    
                    dividend = evaluated_args[0].value
                    divisor = evaluated_args[1].value
                    
                    if divisor == 0:
                        return Expr.Error(
                            category="DivisionError",
                            message="Modulo by zero"
                        )
                    
                    return Expr.Integer(dividend % divisor)

            else:
                evaluated_elements = [self.evaluate_expression(e, env) for e in expr.elements]
                return Expr.ListExpr(evaluated_elements)
            
        elif isinstance(expr, Expr.Function):
            return expr
        
        else:
            raise ValueError(f"Unknown expression type: {type(expr)}")
