from typing import List, Optional


class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements
        
        def __repr__(self):
            if not self.elements:
                return "()"
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner} list)"
        
    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return f"({self.value} symbol)"
        
    class Bytes:
        def __init__(self, value: bytes):
            self.value = value

        def __repr__(self):
            return f"({self.value} bytes)"
        
    class Error:
        def __init__(self, topic: str, origin: Optional['Expr'] = None):
            self.topic = topic
            self.origin  = origin

        def __repr__(self):
            if self.origin is None:
                return f'({self.topic} error)'
            return f'({self.origin} {self.topic} error)'