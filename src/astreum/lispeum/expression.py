from typing import List, Union

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
        """
        Represents an error with a freeform category and message.
        - `category`: A string identifying the type of error (e.g., 'SyntaxError').
        - `message`: A human-readable description of the error.
        - `details`: Optional, additional information about the error.
        """
        def __init__(self, category: str, message: str, details: str = None):
            if not category:
                raise ValueError("Error category must be provided.")
            if not message:
                raise ValueError("Error message must be provided.")
            self.category = category
            self.message = message
            self.details = details

        def __repr__(self):
            if self.details:
                return f'({self.category} "{self.message}" {self.details})'
            return f'({self.category} "{self.message}")'
