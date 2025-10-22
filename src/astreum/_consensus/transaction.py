from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Tuple

from .._storage.atom import Atom, ZERO32
from ..utils.integer import bytes_to_int, int_to_bytes
from .account import Account
from .genesis import TREASURY_ADDRESS
from .receipt import STATUS_FAILED, Receipt, STATUS_SUCCESS


def _make_list(child_ids: List[bytes]) -> Tuple[bytes, List[Atom]]:
    atoms: List[Atom] = []
    next_hash = ZERO32
    chain: List[Atom] = []
    for child_id in reversed(child_ids):
        elem = Atom.from_data(data=child_id, next_hash=next_hash)
        next_hash = elem.object_id()
        chain.append(elem)

    chain.reverse()
    list_value = Atom.from_data(data=len(child_ids).to_bytes(8, "little"), next_hash=next_hash)
    list_type = Atom.from_data(data=b"list", next_hash=list_value.object_id())
    atoms.extend(chain)
    atoms.append(list_value)
    atoms.append(list_type)
    return list_type.object_id(), atoms


@dataclass
class Transaction:
    amount: int
    counter: int
    data: bytes = b""
    recipient: bytes = b""
    sender: bytes = b""
    signature: bytes = b""
    hash: bytes = ZERO32

    def to_atom(self) -> Tuple[bytes, List[Atom]]:
        """Serialise the transaction, returning (object_id, atoms)."""
        body_child_ids: List[bytes] = []
        acc: List[Atom] = []

        def emit(payload: bytes) -> None:
            atom = Atom.from_data(data=payload)
            body_child_ids.append(atom.object_id())
            acc.append(atom)

        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_id, body_atoms = _make_list(body_child_ids)
        acc.extend(body_atoms)

        type_atom = Atom.from_data(data=b"transaction", next_hash=body_id)
        signature_atom = Atom.from_data(data=bytes(self.signature))

        top_list_id, top_atoms = _make_list(
            [type_atom.object_id(), body_id, signature_atom.object_id()]
        )

        atoms: List[Atom] = acc
        atoms.append(type_atom)
        atoms.append(signature_atom)
        atoms.extend(top_atoms)
        return top_list_id, atoms

    @classmethod
    def from_atom(
        cls,
        node: Any,
        transaction_id: bytes,
    ) -> Transaction:
        storage_get = node._local_get
        if not callable(storage_get):
            raise NotImplementedError("node does not expose a storage getter")

        top_type_atom = storage_get(transaction_id)
        if top_type_atom is None or top_type_atom.data != b"list":
            raise ValueError("not a transaction (outer list missing)")

        top_value_atom = storage_get(top_type_atom.next)
        if top_value_atom is None:
            raise ValueError("malformed transaction (outer value missing)")

        head = top_value_atom.next
        first_elem = storage_get(head)
        if first_elem is None:
            raise ValueError("malformed transaction (type element missing)")

        type_atom_id = first_elem.data
        type_atom = storage_get(type_atom_id)
        if type_atom is None or type_atom.data != b"transaction":
            raise ValueError("not a transaction (type mismatch)")

        def read_list_entries(start: bytes) -> List[bytes]:
            entries: List[bytes] = []
            current = start if start != ZERO32 else b""
            while current:
                elem = storage_get(current)
                if elem is None:
                    break
                entries.append(elem.data)
                nxt = elem.next
                current = nxt if nxt != ZERO32 else b""
            return entries

        remainder_entries = read_list_entries(first_elem.next)
        if len(remainder_entries) < 2:
            raise ValueError("malformed transaction (body/signature missing)")

        body_id, signature_atom_id = remainder_entries[0], remainder_entries[1]

        body_type_atom = storage_get(body_id)
        if body_type_atom is None or body_type_atom.data != b"list":
            raise ValueError("malformed transaction body (type)")

        body_value_atom = storage_get(body_type_atom.next)
        if body_value_atom is None:
            raise ValueError("malformed transaction body (value)")

        body_entries = read_list_entries(body_value_atom.next)
        if len(body_entries) < 5:
            body_entries.extend([ZERO32] * (5 - len(body_entries)))

        def read_detail_bytes(entry_id: bytes) -> bytes:
            if entry_id == ZERO32:
                return b""
            elem = storage_get(entry_id)
            if elem is None:
                return b""
            detail_atom = storage_get(elem.data)
            return detail_atom.data if detail_atom is not None else b""

        amount_bytes = read_detail_bytes(body_entries[0])
        counter_bytes = read_detail_bytes(body_entries[1])
        data_bytes = read_detail_bytes(body_entries[2])
        recipient_bytes = read_detail_bytes(body_entries[3])
        sender_bytes = read_detail_bytes(body_entries[4])

        signature_atom = storage_get(signature_atom_id)
        signature_bytes = signature_atom.data if signature_atom is not None else b""

        return cls(
            amount=bytes_to_int(amount_bytes),
            counter=bytes_to_int(counter_bytes),
            data=data_bytes,
            recipient=recipient_bytes,
            sender=sender_bytes,
            signature=signature_bytes,
            hash=bytes(transaction_id),
        )


def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> None:
    """Apply transaction to the candidate block. Override downstream."""
    transaction = Transaction.from_atom(node, transaction_hash)

    accounts = block.accounts

    sender_account = accounts.get_account(address=transaction.sender, node=node)

    if sender_account is None:
        return
    
    tx_cost = 1 + transaction.amount

    if sender_account.balance < tx_cost:
        low_sender_balance_receipt = Receipt(
            transaction_hash=transaction_hash,
            cost=0,
            logs=b"low sender balance",
            status=STATUS_FAILED
        )
        low_sender_balance_receipt.atomize()
        block.receipts.append(receipt)
        block.transactions.append(transaction)
        return

    recipient_account = accounts.get_account(address=transaction.recipient, node=node)

    if recipient_account is None:
        recipient_account = Account.create()

    if transaction.recipient == TREASURY_ADDRESS:
        stake_trie = recipient_account.data
        existing_stake = stake_trie.get(node, transaction.sender)
        current_stake = bytes_to_int(existing_stake)
        new_stake = current_stake + transaction.amount
        stake_trie.put(node, transaction.sender, int_to_bytes(new_stake))
        recipient_account.data_hash = stake_trie.root_hash or ZERO32
        recipient_account.balance += transaction.amount
    else:
        recipient_account.balance += transaction.amount

    sender_account.balance -= tx_cost

    block.accounts.set_account(address=sender_account)

    block.accounts.set_account(address=recipient_account)

    block.transactions.append(transaction)

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        cost=0,
        logs=b"",
        status=STATUS_SUCCESS,
    )
    receipt.atomize()
    block.receipts.append(receipt)
