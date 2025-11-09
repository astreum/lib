from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from .._storage.atom import Atom, AtomKind, ZERO32
from ..utils.integer import bytes_to_int, int_to_bytes
from .account import Account
from .genesis import TREASURY_ADDRESS
from .receipt import STATUS_FAILED, Receipt, STATUS_SUCCESS

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
            atom = Atom.from_data(data=payload, kind=AtomKind.BYTES)
            body_child_ids.append(atom.object_id())
            acc.append(atom)

        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        # Build the linked list of body entry references.
        body_atoms: List[Atom] = []
        body_head = ZERO32
        for child_id in reversed(body_child_ids):
            node = Atom.from_data(data=child_id, next_hash=body_head, kind=AtomKind.BYTES)
            body_head = node.object_id()
            body_atoms.append(node)
        body_atoms.reverse()
        acc.extend(body_atoms)

        body_list_atom = Atom.from_data(data=body_head, kind=AtomKind.LIST)
        acc.append(body_list_atom)
        body_list_id = body_list_atom.object_id()

        signature_atom = Atom.from_data(
            data=bytes(self.signature),
            next_hash=body_list_id,
            kind=AtomKind.BYTES,
        )
        type_atom = Atom.from_data(
            data=b"transaction",
            next_hash=signature_atom.object_id(),
            kind=AtomKind.SYMBOL,
        )

        acc.append(signature_atom)
        acc.append(type_atom)

        self.hash = type_atom.object_id()
        return self.hash, acc

    @classmethod
    def from_atom(
        cls,
        node: Any,
        transaction_id: bytes,
    ) -> Transaction:
        storage_get = getattr(node, "storage_get", None)
        if not callable(storage_get):
            raise NotImplementedError("node does not expose a storage getter")

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

        def _require_atom(
            atom_id: Optional[bytes],
            context: str,
            expected_kind: Optional[AtomKind] = None,
        ) -> Atom:
            if not atom_id or atom_id == ZERO32:
                raise ValueError(f"missing {context}")
            atom = storage_get(atom_id)
            if atom is None:
                raise ValueError(f"missing {context}")
            if expected_kind is not None:
                kind = _atom_kind(atom)
                if kind is not expected_kind:
                    raise ValueError(f"malformed {context}")
            return atom

        def _read_list(head_id: Optional[bytes], context: str) -> List[bytes]:
            entries: List[bytes] = []
            current = head_id if head_id and head_id != ZERO32 else None
            while current:
                node = storage_get(current)
                if node is None:
                    raise ValueError(f"missing list node while decoding {context}")
                node_kind = _atom_kind(node)
                if node_kind is not AtomKind.BYTES:
                    raise ValueError(f"invalid list node while decoding {context}")
                if len(node.data) != len(ZERO32):
                    raise ValueError(f"malformed list entry while decoding {context}")
                entries.append(node.data)
                nxt = node.next
                current = nxt if nxt and nxt != ZERO32 else None
            return entries

        def _read_detail_bytes(entry_id: Optional[bytes]) -> bytes:
            if not entry_id or entry_id == ZERO32:
                return b""
            detail_atom = storage_get(entry_id)
            return detail_atom.data if detail_atom is not None else b""

        type_atom = _require_atom(transaction_id, "transaction type atom", AtomKind.SYMBOL)
        if type_atom.data != b"transaction":
            raise ValueError("not a transaction (type atom payload)")

        signature_atom = _require_atom(type_atom.next, "transaction signature atom", AtomKind.BYTES)
        body_list_atom = _require_atom(signature_atom.next, "transaction body list atom", AtomKind.LIST)
        if body_list_atom.next and body_list_atom.next != ZERO32:
            raise ValueError("malformed transaction (body list tail)")

        body_entry_ids = _read_list(body_list_atom.data, "transaction body")
        if len(body_entry_ids) < 5:
            body_entry_ids.extend([ZERO32] * (5 - len(body_entry_ids)))

        amount_bytes = _read_detail_bytes(body_entry_ids[0])
        counter_bytes = _read_detail_bytes(body_entry_ids[1])
        data_bytes = _read_detail_bytes(body_entry_ids[2])
        recipient_bytes = _read_detail_bytes(body_entry_ids[3])
        sender_bytes = _read_detail_bytes(body_entry_ids[4])

        return cls(
            amount=bytes_to_int(amount_bytes),
            counter=bytes_to_int(counter_bytes),
            data=data_bytes,
            recipient=recipient_bytes,
            sender=sender_bytes,
            signature=signature_atom.data,
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

    block.transactions.append(transaction_hash)

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        cost=0,
        logs=b"",
        status=STATUS_SUCCESS,
    )
    receipt.atomize()
    block.receipts.append(receipt)
