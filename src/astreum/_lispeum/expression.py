from typing import Any, List, Optional

ZERO32 = b"\x00" * 32


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

    @classmethod
    def from_atoms(cls, node: Any, root_hash: bytes) -> "Expr":
        """Rebuild an expression tree from stored atoms."""
        if not isinstance(root_hash, (bytes, bytearray)):
            raise TypeError("root hash must be bytes-like")

        storage_get = getattr(node, "storage_get", None)
        if not callable(storage_get):
            raise TypeError("node must provide a callable 'storage_get'")

        expr_id = bytes(root_hash)

        def _require(atom_id: Optional[bytes], context: str):
            if not atom_id:
                raise ValueError(f"missing atom id while decoding {context}")
            atom = storage_get(atom_id)
            if atom is None:
                raise ValueError(f"missing atom data while decoding {context}")
            return atom

        type_atom = _require(expr_id, "expression type")
        tag = type_atom.data

        if tag == b"symbol":
            val_atom = _require(type_atom.next, "symbol value")
            try:
                return cls.Symbol(val_atom.data.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValueError("symbol atom is not valid utf-8") from exc

        if tag == b"byte":
            val_atom = _require(type_atom.next, "byte payload")
            return cls.Bytes(val_atom.data)

        if tag == b"error":
            topic_atom = _require(type_atom.next, "error topic")
            try:
                topic = topic_atom.data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("error topic is not valid utf-8") from exc
            return cls.Error(topic=topic)

        if tag == b"list":
            val_atom = _require(type_atom.next, "list header")
            if len(val_atom.data) < 8:
                raise ValueError("list length atom too short")
            length = int.from_bytes(val_atom.data[:8], "little", signed=False)
            elements: List[Expr] = []
            next_elem_id = val_atom.next
            for idx in range(length):
                if not next_elem_id or next_elem_id == ZERO32:
                    raise ValueError("list chain shorter than declared length")
                elem_atom = _require(next_elem_id, f"list element {idx}")
                child_hash = elem_atom.data
                child_expr = cls.from_atoms(node, child_hash)
                elements.append(child_expr)
                next_elem_id = elem_atom.next
            return cls.ListExpr(elements)

        raise ValueError("unknown expression type tag")
