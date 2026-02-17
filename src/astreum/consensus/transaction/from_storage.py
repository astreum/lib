from __future__ import annotations

from typing import Any, List, Optional, TYPE_CHECKING

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...utils.integer import bytes_to_int

if TYPE_CHECKING:
    from .model import Transaction


def get_transaction_from_storage(
    node: Any,
    transaction_id: bytes,
) -> "Transaction":
    from .create import create_transaction

    head_atoms = node.get_atom_list(transaction_id)
    if head_atoms is None or len(head_atoms) != 4:
        raise ValueError("malformed transaction head atom list")

    type_atom, version_atom, signature_atom, body_list_atom = head_atoms
    if type_atom.kind is not AtomKind.SYMBOL or type_atom.data != b"transaction":
        raise ValueError("not a transaction (type mismatch)")
    if version_atom.kind is not AtomKind.BYTES:
        raise ValueError("malformed transaction version atom")
    version = bytes_to_int(version_atom.data)
    if version != 1:
        raise ValueError("unsupported transaction version")
    if signature_atom.kind is not AtomKind.BYTES:
        raise ValueError("malformed transaction signature atom")
    if body_list_atom.kind is not AtomKind.LIST:
        raise ValueError("malformed transaction body list atom")
    if body_list_atom.next_id and body_list_atom.next_id != ZERO32:
        raise ValueError("malformed transaction (body list tail)")

    detail_atoms = node.get_atom_list(body_list_atom.data)
    if detail_atoms is None or len(detail_atoms) != 6:
        raise ValueError("malformed transaction body atom list")

    (
        chain_id_atom,
        amount_atom,
        counter_atom,
        data_atom,
        recipient_atom,
        sender_atom,
    ) = detail_atoms
    if any(
        detail_atom.kind is not AtomKind.BYTES
        for detail_atom in (
            chain_id_atom,
            amount_atom,
            counter_atom,
            data_atom,
            recipient_atom,
            sender_atom,
        )
    ):
        raise ValueError("transaction detail atoms must be bytes")

    return create_transaction(
        chain_id=bytes_to_int(chain_id_atom.data),
        amount=bytes_to_int(amount_atom.data),
        counter=bytes_to_int(counter_atom.data),
        data=data_atom.data,
        recipient=recipient_atom.data,
        sender=sender_atom.data,
        signature=signature_atom.data,
        version=version,
        body_hash=body_list_atom.data,
        atom_hash=bytes(transaction_id),
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
