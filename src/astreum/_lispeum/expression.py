from typing import List, Optional


class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements
        
        def __repr__(self):
            if not self.elements:
                return "()"
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"
        
    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return self.value
        
    class Byte:
        def __init__(self, value: int):
            self.value = value

        def __repr__(self):
            return self.value
        
    class Error:
        def __init__(self, topic: str, origin: Optional['Expr'] = None):
            self.topic = topic
            self.origin  = origin

        def __repr__(self):
            if self.origin is None:
                return f'({self.topic} err)'
            return f'({self.origin} {self.topic} err)'