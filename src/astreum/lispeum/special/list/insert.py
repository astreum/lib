from astreum.lispeum.expression import Expr


def handle_list_insert(list: Expr.ListExpr, index: Expr.Integer, value: Expr) -> Expr:
    if not isinstance(list, Expr.ListExpr):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("First argument must be a list")
        ])
    
    if index.value < 0 or index.value > len(list.elements):
        return Expr.ListExpr([
            Expr.ListExpr([]),
            Expr.String("Index out of bounds")
        ])
    
    new_elements = list.elements[:index.value] + [value] + list.elements[index.value:]
    
    return Expr.ListExpr([
        Expr.ListExpr(new_elements),
        Expr.ListExpr([])
    ])
    