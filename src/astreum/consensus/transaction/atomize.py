from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from ...storage.models.atom import Atom, AtomKind
from ...utils.integer import int_to_bytes
from .code import transaction_code_to_bytes

if TYPE_CHECKING:
    from .model import Transaction


def atomize_transaction(transaction: "Transaction") -> Tuple[bytes, List[Atom]]:
    if transaction.signature is None:
        raise ValueError("transaction must be signed before atomization")

    sender_atom = Atom(
        data=bytes(transaction.sender),
        kind=AtomKind.BYTES,
    )
    recipient_atom = Atom(
        data=bytes(transaction.recipient),
        next_id=sender_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    data_atom = Atom(
        data=bytes(transaction.data),
        next_id=recipient_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    counter_atom = Atom(
        data=int_to_bytes(transaction.counter),
        next_id=data_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    code_atom = Atom(
        data=transaction_code_to_bytes(transaction.code),
        next_id=counter_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    amount_atom = Atom(
        data=int_to_bytes(transaction.amount),
        next_id=code_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    chain_id_atom = Atom(
        data=int_to_bytes(transaction.chain_id),
        next_id=amount_atom.object_id(),
        kind=AtomKind.BYTES,
    )

    body_list_atom = Atom(data=chain_id_atom.object_id(), kind=AtomKind.LIST)
    body_list_id = body_list_atom.object_id()

    signature_atom = Atom(
        data=bytes(transaction.signature),
        next_id=body_list_id,
        kind=AtomKind.BYTES,
    )
    version_atom = Atom(
        data=int_to_bytes(transaction.version),
        next_id=signature_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    type_atom = Atom(
        data=b"transaction",
        next_id=version_atom.object_id(),
        kind=AtomKind.SYMBOL,
    )

    atoms = [
        chain_id_atom,
        amount_atom,
        code_atom,
        counter_atom,
        data_atom,
        recipient_atom,
        sender_atom,
        body_list_atom,
        signature_atom,
        version_atom,
        type_atom,
    ]

    transaction.body_hash = chain_id_atom.object_id()
    transaction.atom_hash = type_atom.object_id()
    transaction.hash = transaction.atom_hash
    return transaction.atom_hash, atoms
