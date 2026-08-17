from __future__ import annotations

import time
from typing import TYPE_CHECKING

from blake3 import blake3

from astreum.consensus.transaction import create_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.storage.model import StorageRecord
from astreum.consensus.transaction.storage.payment import _leading_zero_bits, _required_bits
from astreum.crypto.bloom_search import ERA_SIZE
from astreum.expression import Expr, NIL, int_, bytes_, link
from astreum.expression.encoding import encode_expr_to_bytes
from astreum.storage.get.single import get_expr
from astreum.expression.expr import _encode_int
from astreum.storage.radix import get_from_radix_tree

if TYPE_CHECKING:
    from astreum.node import Node


def _compute_pow_and_challenge(
    node: Node,
    expr_id: bytes,
    record: StorageRecord,
) -> tuple[bytes, bytes, int] | None:
    """Compute a PoW claim for the given record.

    Returns (storage_record_id, storage_slot_id, nonce) or None if the
    data is unavailable.
    """
    last_payment_block_hash = record.last_payment_block_hash
    if len(last_payment_block_hash) != 32:
        return None

    # Determine which slot to challenge
    challenge_seed = blake3(last_payment_block_hash + expr_id).digest()
    challenge_index = (
        int.from_bytes(challenge_seed[:8], "little", signed=False) % record.new_count
    )

    # Find the slot at challenge_index by scanning the record's expr list
    record_expr = get_expr(node, expr_id)
    if record_expr is None:
        return None

    # Walk the link list to find the slot at challenge_index
    from astreum.expression import resolve_list_exprs
    slots_expr = get_expr(node, expr_id)
    if slots_expr is None:
        return None

    # The storage_record_id is the expr_id itself (the root hash of the record)
    storage_record_id = expr_id

    # We need to find which storage_slot_id corresponds to challenge_index.
    # The record's expr list in the storage trie contains the slot entries.
    # But StorageRecord doesn't directly store slot IDs — they are stored
    # under their own keys in the storage trie. We need to iterate the storage
    # trie entries that reference this record_hash.
    # For now, use a simpler approach: scan known storage_index entries.
    # The actual slot can be found by looking up the challenge data.
    #
    # In practice, the provider stores the data at storage_slot_id = content_hash.
    # They know which slot to challenge because they track their own slots.
    # We'll look up the slot data from local storage.
    #
    # Since we can't efficiently find the slot_id from the storage trie without
    # iterating all entries, rely on the provider knowing their slots.
    # For the claim worker, we just need to find any slot we're providing.
    # We'll scan the storage_index for entries matching this record.
    storage_slot_id = None
    for sid, provider_id in node.storage_index.items():
        slot_expr = get_expr(node, sid)
        if slot_expr is None:
            continue
        if not slot_expr._tag == "link":
            continue
        # StorageSlot format: Link(head_hash=record_hash, tail=Int(sequence))
        if slot_expr._head_hash == storage_record_id and slot_expr._tail._tag == "int":
            if slot_expr._tail.value == challenge_index:
                storage_slot_id = sid
                break

    if storage_slot_id is None:
        return None

    # Fetch the actual data
    from astreum.storage.get.single.local import get_expr_from_local_storage
    data_expr = get_expr_from_local_storage(node, storage_slot_id)
    if data_expr is None:
        return None

    fetched_data_bytes = encode_expr_to_bytes(data_expr)
    sender_bytes = node.storage_public_key_bytes

    # Compute required bits
    required_bits = _required_bits(
        sender=sender_bytes,
        last_payment_winner=record.last_payment_winner,
        block_height=node.latest_block.height,
        last_payment_height=record.last_payment_height,
        base_bits=0,
    )

    # Brute-force PoW
    nonce = 0
    max_nonce = 1 << 30
    while nonce < max_nonce:
        nonce_encoded = _encode_int(nonce)
        work_hash = blake3(
            last_payment_block_hash
            + sender_bytes
            + storage_record_id
            + storage_slot_id
            + fetched_data_bytes
            + nonce_encoded
        ).digest()
        if _leading_zero_bits(work_hash) >= required_bits:
            return storage_record_id, storage_slot_id, nonce
        nonce += 1

    return None


def _next_claim_counter(node: Node) -> int:
    """Resolve the counter for the next claim tx.

    Uses the greater of the on-chain sender-account counter and the
    node-local ``next_claim_counter`` (bumped after each successful send so
    consecutive eras don't wait for on-chain confirmation). A missing
    account, no latest block, or a fetch failure all mean 0.
    """
    if not hasattr(node, "next_claim_counter"):
        node.next_claim_counter = 0

    latest_block = getattr(node, "latest_block", None)
    on_chain = 0
    if latest_block is not None:
        try:
            account = latest_block.accounts.get_account(
                address=node.storage_public_key_bytes, node=node
            )
            if account is not None:
                on_chain = account.counter
        except Exception:
            pass
    return max(node.next_claim_counter, on_chain)


def _build_multi_claim_tx(
    node: Node,
    claims: list[tuple[bytes, bytes, int]],
    secret_key,
    counter: int,
) -> object:
    """Build a signed STORAGE_PAYMENT transaction with the given claims."""
    claims_expr = NIL
    for storage_record_id, storage_slot_id, nonce in reversed(claims):
        claim = link(
            bytes_(storage_record_id),
            link(
                bytes_(storage_slot_id),
                link(int_(nonce), NIL),
            ),
        )
        claims_expr = link(claim, claims_expr)

    return create_transaction(
        chain_id=node.config["chain_id"],
        sender=node.storage_public_key_bytes,
        counter=counter,
        recipient=b"\x00" * 32,
        code=TransactionCode.STORAGE_PAYMENT,
        amount=0,
        data=claims_expr,
        secret_key=secret_key,
    )


def claim_storage(node: Node) -> None:
    """Submit storage reward claims on era boundaries.

    Runs as a daemon thread.  On each era boundary (every
    ``ERA_SIZE`` blocks) it scans the node's ``storage_index`` for
    records where this node is a provider, computes a proof-of-work
    challenge for each eligible slot, and submits a single
    ``STORAGE_PAYMENT`` transaction bundling all claims.

    Claim spacing uses a progressive back-off when incumbent
    (``claim_spacing_eras``, 1→4 eras) and a wall-drop threshold of
    5 eras for non-incumbent takeover attempts.

    Args:
        node: A fully initialized Node instance with ``storage_index``,
            ``storage_public_key_bytes``, ``storage_secret_key``, and a
            connected P2P communication layer.

    Returns:
        None.  Runs indefinitely until ``communication_stop_event``
        is set.
    """
    stop = node.communication_stop_event
    last_checked_era = -1

    if not hasattr(node, "claim_spacing_eras"):
        node.claim_spacing_eras = {}

    while not stop.is_set():
        latest_block = getattr(node, "latest_block", None)
        if latest_block is None:
            stop.wait(1.0)
            continue

        current_era = latest_block.height // ERA_SIZE
        if current_era == last_checked_era:
            # Wait until next era boundary
            next_boundary = (current_era + 1) * ERA_SIZE
            blocks_remaining = next_boundary - latest_block.height
            wait_seconds = max(1.0, blocks_remaining * 0.5)
            stop.wait(wait_seconds)
            continue

        # Era changed — evaluate all records
        claims_to_make: list[tuple[bytes, bytes, int]] = []
        spacing_eras = node.claim_spacing_eras

        for expr_id, provider_id in list(node.storage_index.items()):
            # Check if we're the provider for this record
            provider_payload = None
            from astreum.storage.providers import provider_payload_for_id
            provider_payload = provider_payload_for_id(node, provider_id)
            if provider_payload is None:
                continue
            # provider_payload is 70 bytes: storage_key(32) + relay_key(32) + IP(4) + port(2)
            if len(provider_payload) < 32:
                continue
            provider_storage_key = provider_payload[:32]
            if provider_storage_key != node.storage_public_key_bytes:
                continue

            # Fetch StorageRecord from storage trie
            contract_head = None
            try:
                from astreum.consensus.constants import STORAGE_ADDRESS
                storage_account = None
                if hasattr(latest_block, "accounts"):
                    storage_account = latest_block.accounts.get_account(STORAGE_ADDRESS, node)
                if storage_account is not None:
                    contract_head = get_from_radix_tree(storage_account.data, node, expr_id)
            except Exception:
                pass

            if not contract_head:
                continue

            record = StorageRecord.from_storage(node, contract_head.hash())
            if record is None:
                continue

            expr_id_key = expr_id
            current_spacing = spacing_eras.get(expr_id_key, 1)
            eras_elapsed = (latest_block.height - record.last_payment_height) // ERA_SIZE

            if record.last_payment_winner == node.storage_public_key_bytes:
                # We're incumbent
                if eras_elapsed >= current_spacing:
                    claim = _compute_pow_and_challenge(node, expr_id, record)
                    if claim is not None:
                        claims_to_make.append(claim)
                        spacing_eras[expr_id_key] = min(current_spacing + 1, 4)
            else:
                # Someone else is incumbent
                spacing_eras[expr_id_key] = 1  # reset
                if eras_elapsed >= 5:  # wall dropping (fib(8)=21, ~2Mx harder)
                    claim = _compute_pow_and_challenge(node, expr_id, record)
                    if claim is not None:
                        claims_to_make.append(claim)

        if claims_to_make:
            try:
                counter = _next_claim_counter(node)
                tx = _build_multi_claim_tx(node, claims_to_make, node.storage_secret_key, counter)
                from astreum.consensus.transaction.send import send_transaction
                send_transaction(node, tx)
                node.next_claim_counter = counter + 1
                node.logger.info(
                    "Claim worker: submitted %d claim(s) in tx %s",
                    len(claims_to_make),
                    tx.hash.hex() if tx.hash else "unknown",
                )
            except Exception as exc:
                node.logger.exception("Claim worker: failed to submit claims: %s", exc)

        last_checked_era = current_era
        stop.wait(0.5)
