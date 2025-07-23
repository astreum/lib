
from typing import List, Optional, Union


class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements

        def __eq__(self, other):
            if not isinstance(other, Expr.ListExpr):
                return NotImplemented
            return self.elements == other.elements

        def __ne__(self, other):
            return not self.__eq__(other)

        @property
        def value(self):
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"


        def __repr__(self):
            if not self.elements:
                return "()"
            
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"
        
        def __iter__(self):
            return iter(self.elements)
        
        def __getitem__(self, index: Union[int, slice]):
            return self.elements[index]

        def __len__(self):
            return len(self.elements)

    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return self.value

    class Integer:
        def __init__(self, value: int):
            self.value = value

        def __repr__(self):
            return str(self.value)

    class String:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return f'"{self.value}"'
        
    class Boolean:
        def __init__(self, value: bool):
            self.value = value

        def __repr__(self):
            return "true" if self.value else "false"

    class Function:
        def __init__(self, params: List[str], body: 'Expr'):
            self.params = params
            self.body = body

        def __repr__(self):
            params_str = " ".join(self.params)
            body_str = str(self.body)
            return f"(fn ({params_str}) {body_str})"

    class Error:
        def __init__(self, message: str, origin: Optional['Expr'] = None):
            self.message = message
            self.origin  = origin

        def __repr__(self):
            if self.origin is None:
                return f'(error "{self.message}")'
            return f'(error "{self.message}" in {self.origin})'
