from typing import Any, List, Optional, Tuple

from ...storage.models.atom import Atom, AtomKind

ZERO32 = b"\x00" * 32
ERROR_SYMBOL = "error"


class Expr:
    class ListExpr:
        def __init__(self, elements: List['Expr']):
            self.elements = elements
        
        def __repr__(self):
            if not self.elements:
                return "()"
            inner = " ".join(str(e) for e in self.elements)
            return f"({inner})"

        def to_atoms(self):
            return Expr.to_atoms(self)
        
    class Symbol:
        def __init__(self, value: str):
            self.value = value

        def __repr__(self):
            return f"{self.value}"

        def to_atoms(self):
            return Expr.to_atoms(self)
        
    class Bytes:
        def __init__(self, value: bytes):
            self.value = value

        def __repr__(self):
            int_value = int.from_bytes(self.value, "big") if self.value else 0
            return f"{int_value}"

        def to_atoms(self):
            return Expr.to_atoms(self)
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

        def _atom_kind(atom: Any) -> Optional[AtomKind]:
            kind_value = getattr(atom, "kind", None)
            if isinstance(kind_value, AtomKind):
                return kind_value
            if isinstance(kind_value, int):
                try:
                    return AtomKind(kind_value)
                except ValueError:
                    return None
            return None

        type_atom = _require(expr_id, "expression atom")

        kind_enum = _atom_kind(type_atom)
        if kind_enum is None:
            raise ValueError("expression atom missing kind")

        if kind_enum is AtomKind.SYMBOL:
            try:
                return cls.Symbol(type_atom.data.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise ValueError("symbol atom is not valid utf-8") from exc

        if kind_enum is AtomKind.BYTES:
            return cls.Bytes(type_atom.data)

        if kind_enum is AtomKind.LIST:
            # Empty list sentinel: zero-length payload and no next pointer.
            if len(type_atom.data) == 0 and type_atom.next_id == ZERO32:
                return cls.ListExpr([])

            elements: List[Expr] = []
            current_atom = type_atom
            idx = 0
            while True:
                child_hash = current_atom.data
                if not child_hash:
                    raise ValueError("list element missing child hash")
                if len(child_hash) != len(ZERO32):
                    raise ValueError("list element hash has unexpected length")
                child_expr = cls.from_atoms(node, child_hash)
                elements.append(child_expr)
                next_id = current_atom.next_id
                if next_id == ZERO32:
                    break
                next_atom = _require(next_id, f"list element {idx}")
                next_kind = _atom_kind(next_atom)
                if next_kind is not AtomKind.LIST:
                    raise ValueError("list chain contains non-list atom")
                current_atom = next_atom
                idx += 1
            return cls.ListExpr(elements)

        raise ValueError(f"unknown expression kind: {kind_enum}")

    @staticmethod
    def to_atoms(e: "Expr") -> Tuple[bytes, List[Atom]]:
        def symbol(value: str) -> Tuple[bytes, List[Atom]]:
            atom = Atom(
                data=value.encode("utf-8"),
                kind=AtomKind.SYMBOL,
            )
            return atom.object_id(), [atom]

        def bytes_value(data: bytes) -> Tuple[bytes, List[Atom]]:
            atom = Atom(
                data=data,
                kind=AtomKind.BYTES,
            )
            return atom.object_id(), [atom]

        def lst(items: List["Expr"]) -> Tuple[bytes, List[Atom]]:
            acc: List[Atom] = []
            child_hashes: List[bytes] = []
            for it in items:
                h, atoms = Expr.to_atoms(it)
                acc.extend(atoms)
                child_hashes.append(h)
            next_hash = ZERO32
            elem_atoms: List[Atom] = []
            for h in reversed(child_hashes):
                a = Atom(data=h, next_id=next_hash, kind=AtomKind.LIST)
                next_hash = a.object_id()
                elem_atoms.append(a)
            elem_atoms.reverse()
            if elem_atoms:
                head = elem_atoms[0].object_id()
            else:
                empty_atom = Atom(data=b"", kind=AtomKind.LIST)
                elem_atoms = [empty_atom]
                head = empty_atom.object_id()
            return head, acc + elem_atoms

        if isinstance(e, Expr.Symbol):
            return symbol(e.value)
        if isinstance(e, Expr.Bytes):
            return bytes_value(e.value)
        if isinstance(e, Expr.ListExpr):
            return lst(e.elements)
        raise TypeError("unknown Expr variant")

def _expr_generate_id(expr) -> bytes:
    expr_id, _ = Expr.to_atoms(expr)
    return expr_id


def _expr_cached_id(expr) -> bytes:
    cached = getattr(expr, "_cached_id", None)
    if cached is None:
        cached = _expr_generate_id(expr)
        setattr(expr, "_cached_id", cached)
    return cached


for _expr_cls in (Expr.ListExpr, Expr.Symbol, Expr.Bytes):
    _expr_cls.generate_id = _expr_generate_id  # type: ignore[attr-defined]
    _expr_cls.id = property(_expr_cached_id)  # type: ignore[attr-defined]


def error_expr(topic: str, message: str) -> Expr.ListExpr:
    """Encode an error as (error <topic-bytes> <message-bytes>)."""
    try:
        topic_bytes = topic.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("error topic must be valid utf-8") from exc
    try:
        message_bytes = message.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("error message must be valid utf-8") from exc
    return Expr.ListExpr([
        Expr.Symbol(ERROR_SYMBOL),
        Expr.Bytes(topic_bytes),
        Expr.Bytes(message_bytes),
    ])

def get_expr_list_from_storage(self, key: bytes) -> Optional["ListExpr"]:
        """Load a list expression from storage using the given atom list root hash."""
        atoms = self.get_atom_list_from_storage(root_hash=key)
        if atoms is None:
            return None
        
        expr_list = []
        for atom in atoms:
            match atom.kind:
                case AtomKind.SYMBOL:
                    expr_list.append(Expr.Symbol(atom.data))
                case AtomKind.BYTES:
                    expr_list.append(Expr.Bytes(atom.data))
                case AtomKind.LIST:
                    expr_list.append(Expr.ListExpr([
                        Expr.Bytes(atom.data),
                        Expr.Symbol("ref")
                    ]))

        expr_list.reverse()
        return Expr.ListExpr(expr_list)
