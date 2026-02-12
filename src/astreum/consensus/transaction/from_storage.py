from __future__ import annotations

from typing import Any, List, Optional, TYPE_CHECKING

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...utils.integer import bytes_to_int

if TYPE_CHECKING:
    from .model import Transaction


def _atom_kind(atom: Optional[Atom]) -> Optional[AtomKind]:
    kind_value = getattr(atom, "kind", None)
    if isinstance(kind_value, AtomKind):
        return kind_value
    if isinstance(kind_value, int):
        try:
            return AtomKind(kind_value)
        except ValueError:
            return None
    return None


def load_transaction_from_storage(
    cls: type["Transaction"],
    node: Any,
    transaction_id: bytes,
) -> "Transaction":
    get_atom = getattr(node, "get_atom", None)
    if not callable(get_atom):
        raise NotImplementedError("node does not expose an atom getter")

    def _require_atom(
        atom_id: Optional[bytes],
        context: str,
        expected_kind: Optional[AtomKind] = None,
    ) -> Atom:
        if not atom_id or atom_id == ZERO32:
            raise ValueError(f"missing {context}")
        atom = get_atom(atom_id)
        if atom is None:
            raise ValueError(f"missing {context}")
        if expected_kind is not None:
            kind = _atom_kind(atom)
            if kind is not expected_kind:
                raise ValueError(f"malformed {context}")
        return atom

    type_atom = _require_atom(transaction_id, "transaction type atom", AtomKind.SYMBOL)
    if type_atom.data != b"transaction":
        raise ValueError("not a transaction (type atom payload)")

    version_atom = _require_atom(type_atom.next_id, "transaction version atom", AtomKind.BYTES)
    version = bytes_to_int(version_atom.data)
    if version != 1:
        raise ValueError("unsupported transaction version")

    signature_atom = _require_atom(
        version_atom.next_id,
        "transaction signature atom",
        AtomKind.BYTES,
    )
    body_list_atom = _require_atom(signature_atom.next_id, "transaction body list atom", AtomKind.LIST)
    if body_list_atom.next_id and body_list_atom.next_id != ZERO32:
        raise ValueError("malformed transaction (body list tail)")

    detail_atoms = node.get_atom_list(body_list_atom.data)
    if detail_atoms is None:
        raise ValueError("missing transaction body list nodes")
    if len(detail_atoms) != 6:
        raise ValueError("transaction body must contain exactly 6 detail entries")

    detail_values: List[bytes] = []
    for detail_atom in detail_atoms:
        if detail_atom.kind is not AtomKind.BYTES:
            raise ValueError("transaction detail atoms must be bytes")
        detail_values.append(detail_atom.data)

    (
        chain_id_bytes,
        amount_bytes,
        counter_bytes,
        data_bytes,
        recipient_bytes,
        sender_bytes,
    ) = detail_values

    return cls(
        chain_id=bytes_to_int(chain_id_bytes),
        amount=bytes_to_int(amount_bytes),
        counter=bytes_to_int(counter_bytes),
        data=data_bytes,
        recipient=recipient_bytes,
        sender=sender_bytes,
        signature=signature_atom.data,
        hash=bytes(transaction_id),
        version=version,
    )


def load_transaction_atoms(
    node: Any,
    transaction_id: bytes,
) -> Optional[List[Atom]]:
    """Load the transaction atom chain from storage, returning the atoms or None."""
    atoms = node.get_atom_list(transaction_id)
    if atoms is None or len(atoms) < 4:
        return None
    type_atom = atoms[0]
    if type_atom.kind is not AtomKind.SYMBOL or type_atom.data != b"transaction":
        return None
    version_atom = atoms[1]
    if version_atom.kind is not AtomKind.BYTES or bytes_to_int(version_atom.data) != 1:
        return None

    body_list_atom = atoms[-1]
    detail_atoms = node.get_atom_list(body_list_atom.data)
    if detail_atoms is None:
        return None
    atoms.extend(detail_atoms)

    return atoms
