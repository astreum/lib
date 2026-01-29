from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...storage.cold.insert import insert_atom_into_cold_storage
from ...utils.integer import bytes_to_int, int_to_bytes
from .account import Account
from ..constants import TREASURY_ADDRESS
from .receipt import STATUS_FAILED, Receipt, STATUS_SUCCESS

@dataclass
class Transaction:
    chain_id: int
    amount: int
    counter: int
    version: int = 1
    data: bytes = b""
    recipient: bytes = b""
    sender: bytes = b""
    signature: bytes = b""
    hash: bytes = ZERO32

    def sign(self, private_key: Any) -> bytes:
        """Sign the transaction detail list head and store the signature."""
        detail_payloads: List[bytes] = []

        def emit(payload: bytes) -> None:
            detail_payloads.append(payload)

        emit(int_to_bytes(self.chain_id))
        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_head = ZERO32
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            body_head = atom.object_id()

        self.signature = private_key.sign(body_head)
        return body_head

    def atomize(self) -> Tuple[bytes, List[Atom]]:
        """Serialise the transaction, returning (object_id, atoms)."""
        detail_payloads: List[bytes] = []
        acc: List[Atom] = []

        def emit(payload: bytes) -> None:
            detail_payloads.append(payload)

        emit(int_to_bytes(self.chain_id))
        emit(int_to_bytes(self.amount))
        emit(int_to_bytes(self.counter))
        emit(bytes(self.data))
        emit(bytes(self.recipient))
        emit(bytes(self.sender))

        body_head = ZERO32
        detail_atoms: List[Atom] = []
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            detail_atoms.append(atom)
            body_head = atom.object_id()
        detail_atoms.reverse()
        acc.extend(detail_atoms)

        body_list_atom = Atom(data=body_head, kind=AtomKind.LIST)
        acc.append(body_list_atom)
        body_list_id = body_list_atom.object_id()

        signature_atom = Atom(
            data=bytes(self.signature),
            next_id=body_list_id,
            kind=AtomKind.BYTES,
        )
        version_atom = Atom(
            data=int_to_bytes(self.version),
            next_id=signature_atom.object_id(),
            kind=AtomKind.BYTES,
        )
        type_atom = Atom(
            data=b"transaction",
            next_id=version_atom.object_id(),
            kind=AtomKind.SYMBOL,
        )

        acc.append(signature_atom)
        acc.append(version_atom)
        acc.append(type_atom)

        self.hash = type_atom.object_id()
        return self.hash, acc

    @classmethod
    def from_storage(
        cls,
        node: Any,
        transaction_id: bytes,
    ) -> Transaction:
        get_atom = getattr(node, "get_atom", None)
        if not callable(get_atom):
            raise NotImplementedError("node does not expose an atom getter")

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

    @classmethod
    def get_atoms(
        cls,
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


def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> int:
    """Apply transaction to the candidate block and return the collected fee."""
    transaction = Transaction.from_storage(node, transaction_hash)

    block_chain = getattr(block, "chain_id", None)
    if block_chain is not None and transaction.chain_id != block_chain:
        return 0

    accounts = getattr(block, "accounts", None)
    if accounts is None:
        raise ValueError("block missing accounts snapshot for transaction application")

    sender_account = accounts.get_account(address=transaction.sender, node=node)
    if sender_account is None:
        return 0

    tx_fee = 1
    tx_cost = tx_fee + transaction.amount

    if sender_account.balance < tx_cost:
        low_sender_balance_receipt = Receipt(
            transaction_hash=bytes(transaction_hash),
            cost=0,
            status=STATUS_FAILED,
        )
        low_sender_balance_receipt.atomize()
        if block.receipts is None:
            block.receipts = []
        block.receipts.append(low_sender_balance_receipt)
        if block.transactions is None:
            block.transactions = []
        block.transactions.append(transaction)
        return 0

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
    accounts.set_account(transaction.sender, sender_account)
    accounts.set_account(transaction.recipient, recipient_account)

    if block.transactions is None:
        block.transactions = []
    block.transactions.append(transaction)

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        cost=tx_fee,
        status=STATUS_SUCCESS,
    )
    receipt.atomize()
    if block.receipts is None:
        block.receipts = []
    block.receipts.append(receipt)
    return tx_fee

def send_transaction(
    node: "Node",
    receipient_public_key: bytes,
    sender_secret_key: bytes,
    amount: int
):
    if not getattr(node, "is_connected", False):
        raise RuntimeError("node not connected")

    latest_block = getattr(node, "latest_block", None)
    if latest_block is None:
        raise RuntimeError("latest block unavailable")

    import time
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from ...communication.handlers.object_response import OBJECT_FOUND_LIST_PAYLOAD
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing
    from ...storage.advertisments import advertise_atoms
    from .accounts import Accounts

    sender_key = Ed25519PrivateKey.from_private_bytes(bytes(sender_secret_key))
    sender_public_key_bytes = sender_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    accounts = Accounts(root_hash=getattr(latest_block, "accounts_hash", None))
    sender_account = accounts.get_account(address=sender_public_key_bytes, node=node)
    sender_counter = sender_account.counter if sender_account is not None else 0

    transaction = Transaction(
        chain_id=int(node.config.get("chain_id", 0)),
        amount=int(amount),
        counter=sender_counter + 1,
        data=b"",
        recipient=bytes(receipient_public_key),
        sender=sender_public_key_bytes,
    )
    body_head = transaction.sign(sender_key)
    tx_hash, atoms = transaction.atomize()

    for atom in atoms:
        atom_id = atom.object_id()
        node._hot_storage_set(atom_id, atom)
        insert_atom_into_cold_storage(node, atom)

    ttl_seconds = int(node.config["peer_timeout"])
    expires_at = time.time() + ttl_seconds if ttl_seconds > 0 else None
    entries = []
    for atom_id in (tx_hash, body_head):
        if atom_id and atom_id != ZERO32:
            entries.append((atom_id, OBJECT_FOUND_LIST_PAYLOAD, expires_at))
    if entries:
        node.add_atom_advertisements(entries)
        advertise_atoms(node, entries=entries)

    validation_route = getattr(node, "validation_route", None)
    if validation_route is None:
        raise RuntimeError("no validator available")

    has_validators = bool(getattr(validation_route, "peers", None))
    if not has_validators:
        peers = []
        peers_lock = getattr(node, "peers_lock", None)
        if peers_lock is not None:
            with peers_lock:
                peers = list(getattr(node, "peers", {}).items())
        else:
            peers = list(getattr(node, "peers", {}).items())

        for _peer_key, peer in peers:
            if not getattr(peer, "address", None):
                continue
            route_request = Message(
                topic=MessageTopic.ROUTE_REQUEST,
                content=b"\x01",
                sender=node.relay_public_key,
            )
            route_request.encrypt(peer.shared_key_bytes)
            enqueue_outgoing(
                node,
                peer.address,
                message=route_request,
                difficulty=peer.difficulty,
            )

        wait_deadline = time.time() + float(node.config.get("peer_timeout_interval", 10))
        while time.time() < wait_deadline:
            if getattr(validation_route, "peers", None):
                has_validators = True
                break
            time.sleep(0.1)

    if not has_validators:
        raise RuntimeError("no validator available")

    validators = {}
    for peer in validation_route.peers.values():
        if peer is not None and getattr(peer, "address", None):
            validators[getattr(peer, "public_key_bytes", None)] = peer
    for bucket in validation_route.buckets.values():
        for peer_key in bucket:
            peer = node.get_peer(peer_key)
            if peer is not None and getattr(peer, "address", None):
                validators[peer.public_key_bytes] = peer

    if not validators:
        raise RuntimeError("no validator available")

    for peer in validators.values():
        tx_message = Message(
            topic=MessageTopic.TRANSACTION,
            content=bytes(tx_hash),
            sender=node.relay_public_key,
        )
        tx_message.encrypt(peer.shared_key_bytes)
        enqueue_outgoing(
            node,
            peer.address,
            message=tx_message,
            difficulty=peer.difficulty,
        )

    return tx_hash
