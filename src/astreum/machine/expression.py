from typing import List

class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements

        @property
        def value(self):
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"


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

    class Function:
        def __init__(self, params: List[str], body: 'Expr'):
            self.params = params
            self.body = body

        def __repr__(self):
            params_str = " ".join(self.params)
            body_str = str(self.body)
            return f"(fn ({params_str}) {body_str})"