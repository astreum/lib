
from __future__ import annotations

from typing import Any, Iterable, List, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .account import Account
from .block import Block
from .._storage.atom import Atom, ZERO32
from .._storage.patricia import PatriciaTrie, PatriciaNode

TREASURY_ADDRESS = b"\x01" * 32
BURN_ADDRESS = b"\x00" * 32


def _int_to_be_bytes(value: int) -> bytes:
    if value < 0:
        raise ValueError("integer fields in genesis must be non-negative")
    if value == 0:
        return b"\x00"
    length = (value.bit_length() + 7) // 8
    return value.to_bytes(length, "big")


def _make_list(child_ids: List[bytes]) -> Tuple[bytes, List[Atom]]:
    next_hash = ZERO32
    chain: List[Atom] = []
    for child_id in reversed(child_ids):
        elem = Atom.from_data(data=child_id, next_hash=next_hash)
        next_hash = elem.object_id()
        chain.append(elem)
    chain.reverse()

    value_atom = Atom.from_data(
        data=len(child_ids).to_bytes(8, "little"),
        next_hash=next_hash,
    )
    type_atom = Atom.from_data(data=b"list", next_hash=value_atom.object_id())
    atoms = chain + [value_atom, type_atom]
    return type_atom.object_id(), atoms


def _store_atoms(node: Any, atoms: Iterable[Atom]) -> None:
    setter = getattr(node, "_local_set", None)
    if not callable(setter):
        raise TypeError("node must expose '_local_set(object_id, atom)'")
    for atom in atoms:
        setter(atom.object_id(), atom)


def _persist_trie(trie: PatriciaTrie, node: Any) -> None:
    for patricia_node in trie.nodes.values():
        _, atoms = patricia_node.to_atoms()
        _store_atoms(node, atoms)


if not hasattr(PatriciaNode, "to_bytes"):
    def _patricia_node_to_bytes(self: PatriciaNode) -> bytes:  # type: ignore[no-redef]
        fields = [
            bytes([self.key_len]) + self.key,
            self.child_0 or ZERO32,
            self.child_1 or ZERO32,
            self.value or b"",
        ]
        encoded: List[bytes] = []
        for field in fields:
            encoded.append(len(field).to_bytes(4, "big"))
            encoded.append(field)
        return b"".join(encoded)

    PatriciaNode.to_bytes = _patricia_node_to_bytes  # type: ignore[attr-defined]


def create_genesis_block(node: Any, validator_public_key: bytes, validator_secret_key: bytes) -> Block:
    validator_pk = bytes(validator_public_key)

    if len(validator_pk) != 32:
        raise ValueError("validator_public_key must be 32 bytes")

    # 1. Stake trie with single validator stake of 1 (encoded on 32 bytes).
    stake_trie = PatriciaTrie()
    stake_amount = (1).to_bytes(32, "big")
    stake_trie.put(node, validator_pk, stake_amount)
    _persist_trie(stake_trie, node)
    stake_root = stake_trie.root_hash or ZERO32

    # 2. Account trie with treasury, burn, and validator accounts.
    accounts_trie = PatriciaTrie()

    treasury_account = Account.create(balance=1, data=stake_root, counter=0)
    treasury_account_id, treasury_atoms = treasury_account.to_atom()
    _store_atoms(node, treasury_atoms)
    accounts_trie.put(node, TREASURY_ADDRESS, treasury_account_id)

    burn_account = Account.create(balance=0, data=b"", counter=0)
    burn_account_id, burn_atoms = burn_account.to_atom()
    _store_atoms(node, burn_atoms)
    accounts_trie.put(node, BURN_ADDRESS, burn_account_id)

    validator_account = Account.create(balance=0, data=b"", counter=0)
    validator_account_id, validator_atoms = validator_account.to_atom()
    _store_atoms(node, validator_atoms)
    accounts_trie.put(node, validator_pk, validator_account_id)

    _persist_trie(accounts_trie, node)

    accounts_root = accounts_trie.root_hash
    if accounts_root is None:
        raise ValueError("genesis accounts trie is empty")

    # 3. Assemble block metadata.
    block = Block()
    block.previous_block_hash = ZERO32
    block.number = 0
    block.timestamp = 0
    block.accounts_hash = accounts_root
    block.accounts = accounts_trie
    block.transactions_total_fees = 0
    block.transactions_hash = ZERO32
    block.receipts_hash = ZERO32
    block.delay_difficulty = 0
    block.delay_output = b""
    block.validator_public_key = validator_pk
    block.transactions = []
    block.receipts = []

    # 4. Sign the block body with the validator secret key.
    block.signature = b""
    block.to_atom()

    if block.body_hash is None:
        raise ValueError("failed to materialise genesis block body")

    secret = Ed25519PrivateKey.from_private_bytes(validator_secret_key)
    block.signature = secret.sign(block.body_hash)
    block_hash, block_atoms = block.to_atom()
    _store_atoms(node, block_atoms)

    block.hash = block_hash
    return block
