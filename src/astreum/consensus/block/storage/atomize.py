from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from ....storage.models.atom import Atom, AtomKind

if TYPE_CHECKING:
    from ....validation.models.block import Block


def _int_to_be_bytes(value: int | None) -> bytes:
    if value is None:
        return b""
    value = int(value)
    if value == 0:
        return b"\x00"
    size = (value.bit_length() + 7) // 8
    return value.to_bytes(size, "big")


def atomize_block(block: "Block") -> Tuple[bytes, List[Atom]]:
    nonce_atom = Atom(
        data=_int_to_be_bytes(block.nonce),
        kind=AtomKind.BYTES,
    )
    validator_public_key_atom = Atom(
        data=block.validator_public_key_bytes or b"",
        next_id=nonce_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    receipts_hash_atom = Atom(
        data=block.receipts_hash or b"",
        next_id=validator_public_key_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    transactions_hash_atom = Atom(
        data=block.transactions_hash or b"",
        next_id=receipts_hash_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    accounts_hash_atom = Atom(
        data=block.accounts_hash or b"",
        next_id=transactions_hash_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    total_storage_fee_atom = Atom(
        data=_int_to_be_bytes(block.total_storage_fee),
        next_id=accounts_hash_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    total_transaction_fee_atom = Atom(
        data=_int_to_be_bytes(block.total_transaction_fee),
        next_id=total_storage_fee_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    cumulative_storage_fee_atom = Atom(
        data=_int_to_be_bytes(block.cumulative_storage_fee),
        next_id=total_transaction_fee_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    cumulative_transaction_fee_atom = Atom(
        data=_int_to_be_bytes(block.cumulative_transaction_fee),
        next_id=cumulative_storage_fee_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    cumulative_mint_atom = Atom(
        data=_int_to_be_bytes(block.cumulative_mint),
        next_id=cumulative_transaction_fee_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    cumulative_burn_atom = Atom(
        data=_int_to_be_bytes(block.cumulative_burn),
        next_id=cumulative_mint_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    cumulative_stake_atom = Atom(
        data=_int_to_be_bytes(block.cumulative_stake),
        next_id=cumulative_burn_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    difficulty_atom = Atom(
        data=_int_to_be_bytes(block.difficulty),
        next_id=cumulative_stake_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    timestamp_atom = Atom(
        data=_int_to_be_bytes(block.timestamp),
        next_id=difficulty_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    previous_block_hash_atom = Atom(
        data=block.previous_block_hash,
        next_id=timestamp_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    height_atom = Atom(
        data=_int_to_be_bytes(block.height),
        next_id=previous_block_hash_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    chain_id_atom = Atom(
        data=_int_to_be_bytes(block.chain_id),
        next_id=height_atom.object_id(),
        kind=AtomKind.BYTES,
    )

    body_list_atom = Atom(data=chain_id_atom.object_id(), kind=AtomKind.LIST)
    block.body_hash = body_list_atom.object_id()

    sig_atom = Atom(
        data=bytes(block.signature or b""),
        next_id=block.body_hash,
        kind=AtomKind.BYTES,
    )
    version_atom = Atom(
        data=_int_to_be_bytes(block.version),
        next_id=sig_atom.object_id(),
        kind=AtomKind.BYTES,
    )
    type_atom = Atom(
        data=b"block",
        next_id=version_atom.object_id(),
        kind=AtomKind.SYMBOL,
    )

    atoms = [
        chain_id_atom,
        height_atom,
        previous_block_hash_atom,
        timestamp_atom,
        difficulty_atom,
        cumulative_stake_atom,
        cumulative_burn_atom,
        cumulative_mint_atom,
        cumulative_transaction_fee_atom,
        cumulative_storage_fee_atom,
        total_transaction_fee_atom,
        total_storage_fee_atom,
        accounts_hash_atom,
        transactions_hash_atom,
        receipts_hash_atom,
        validator_public_key_atom,
        nonce_atom,
        body_list_atom,
        sig_atom,
        version_atom,
        type_atom,
    ]

    block.atom_hash = type_atom.object_id()
    return block.atom_hash, atoms
