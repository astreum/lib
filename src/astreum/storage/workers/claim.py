from __future__ import annotations

import time
from typing import TYPE_CHECKING

from blake3 import blake3

from astreum.consensus.transaction import create_transaction
from astreum.consensus.transaction.code import TransactionCode
from astreum.consensus.transaction.storage.model import StorageRecord
from astreum.consensus.transaction.storage.payment import _leading_zero_bits, _required_bits
from astreum.crypto.bloom_search import ERA_SIZE
from astreum.expression import Expr, NIL, int_, bytes_, link, RESOLUTION_SINGLE, ZERO32
from astreum.expression import get_expr_tag, get_expr_value
from astreum.expression.encoding import encode_expr_to_bytes
from astreum.storage.actions.set import add_expr_advertisement
from astreum.storage.get.list import list_exprs_in_cold_storage
from astreum.expression.expr import _encode_int
from astreum.storage.radix import get_from_radix_tree

if TYPE_CHECKING:
    from astreum.node import Node


def _build_inverse_view(node: Node) -> dict[bytes, dict[int, bytes]]:
    """Map ``storage_record_id -> {sequence: slot_expr_id}`` from the registry.

    Built lazily each era from ``node.storage_slot_registry`` so it cannot
    drift from what this node actually holds.  A record id that is absent (or
    has no slot at the challenged sequence) means we don't hold that slot.
    """
    inverse: dict[bytes, dict[int, bytes]] = {}
    for slot_expr_id, (record_id, sequence) in node.storage_slot_registry.items():
        seq_map = inverse.setdefault(record_id, {})
        seq_map[sequence] = slot_expr_id
    return inverse


def _compute_pow_and_challenge(
    node: Node,
    expr_id: bytes,
    record: StorageRecord,
    inverse_view: dict[bytes, dict[int, bytes]],
) -> tuple[bytes, bytes, int] | None:
    """Compute a PoW claim for the given record.

    Returns (storage_record_id, storage_slot_id, nonce) or None if the
    data is unavailable.
    """
    last_payment_block_hash = record.last_payment_block_hash
    if len(last_payment_block_hash) != 32:
        return None
    if record.new_count <= 0:
        return None

    # Determine which slot to challenge
    challenge_seed = blake3(last_payment_block_hash + expr_id).digest()
    challenge_index = (
        int.from_bytes(challenge_seed[:8], "little", signed=False) % record.new_count
    )

    # Resolve the challenged slot via the registry's inverse view.  The
    # storage_record_id is the expr_id itself (the root hash of the record).
    storage_slot_id = inverse_view.get(expr_id, {}).get(challenge_index)
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
    storage_record_id = expr_id
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


def _recover_one(
    node: Node,
    expr_id: bytes,
    value: Expr,
    records_held: set[bytes],
) -> None:
    """Classify a recovered cold expr and rebuild in-memory state for it.

    ``value`` is the expr retrieved from the storage radix for ``expr_id``.
    A ``StorageSlot`` (Link(record_hash, Int(sequence))) updates the registry
    and tracks its record; a ``StorageRecord`` header tracks its record id.
    Both get an ``expr_advertisements`` entry so the advertiser re-announces
    them.  Recovered records start at the conservative incumbent spacing of 4
    eras (the chain does not remember local backoff state).
    """
    if value is None or value._tag != "link":
        return
    head_hash = value._head_hash
    tail = value._tail
    if (
        head_hash is not None
        and head_hash != ZERO32
        and tail is not None
        and get_expr_tag(tail, node) == "int"
    ):
        # StorageSlot: Link(record_hash, Int(sequence))
        node.storage_slot_registry[expr_id] = (head_hash, get_expr_value(tail, node))
        records_held.add(head_hash)
        node.claim_spacing_eras[head_hash] = 4
        add_expr_advertisement(node, expr_id, RESOLUTION_SINGLE)
        node.logger.debug(
            "Cold-storage recovery: slot %s -> record %s seq %d",
            expr_id.hex(),
            head_hash.hex(),
            get_expr_value(tail, node),
        )
        return
    # StorageRecord header
    record_id = value.hash()
    record = StorageRecord.from_storage(node, record_id)
    if record is not None:
        records_held.add(record_id)
        node.claim_spacing_eras[record_id] = 4
        add_expr_advertisement(node, record_id, RESOLUTION_SINGLE)
        node.logger.debug("Cold-storage recovery: record %s", record_id.hex())


def _build_claims_for_records(
    node: Node,
    latest_block,
    record_ids: set[bytes],
    spacing_eras: dict[bytes, int],
) -> list[tuple[bytes, bytes, int]]:
    """Evaluate every held record and build eligible claims for this era."""
    claims_to_make: list[tuple[bytes, bytes, int]] = []
    inverse_view = _build_inverse_view(node)
    from astreum.consensus.constants import STORAGE_ADDRESS

    for record_id in record_ids:
        contract_head = None
        try:
            storage_account = None
            if hasattr(latest_block, "accounts"):
                storage_account = latest_block.accounts.get_account(STORAGE_ADDRESS, node)
            if storage_account is not None:
                contract_head = get_from_radix_tree(storage_account.data, node, record_id)
        except Exception:
            continue
        if not contract_head:
            continue

        record = StorageRecord.from_storage(node, contract_head.hash())
        if record is None:
            continue

        current_spacing = spacing_eras.get(record_id, 1)
        eras_elapsed = (latest_block.height - record.last_payment_height) // ERA_SIZE

        if record.last_payment_winner == node.storage_public_key_bytes:
            # We're incumbent
            if eras_elapsed >= current_spacing:
                claim = _compute_pow_and_challenge(node, record_id, record, inverse_view)
                if claim is not None:
                    claims_to_make.append(claim)
                    spacing_eras[record_id] = min(current_spacing + 1, 4)
        else:
            # Someone else is incumbent
            spacing_eras[record_id] = 1  # reset
            if eras_elapsed >= 5:  # wall dropping (fib(8)=21, ~2Mx harder)
                claim = _compute_pow_and_challenge(node, record_id, record, inverse_view)
                if claim is not None:
                    claims_to_make.append(claim)
    return claims_to_make


def _submit_claims(node: Node, claims_to_make: list[tuple[bytes, bytes, int]]) -> None:
    """Bundle the given claims into a single STORAGE_PAYMENT tx and send it."""
    if not claims_to_make:
        return
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


def _run_cold_recovery(node: Node) -> int:
    """One-shot cold-boot recovery, interleaved with era-boundary claims.

    Scans cold storage, rebuilds ``storage_slot_registry``,
    ``storage_records_held``, and ``expr_advertisements``, and runs the
    registry-driven claim pass whenever the era rolls over.  Returns the last
    era checked so the caller can pick up without double-claiming.
    """
    latest_block = getattr(node, "latest_block", None)
    if latest_block is None:
        return -1

    try:
        exprs = list_exprs_in_cold_storage(node)
    except Exception as exc:
        node.logger.exception("Cold-storage recovery: enumeration failed: %s", exc)
        return -1

    if not exprs:
        node.logger.debug("Cold-storage recovery: nothing to recover")
        return -1

    node.logger.info("Cold-storage recovery: scanning %d cold expr(s)", len(exprs))
    spacing_eras = node.claim_spacing_eras
    records_held: set[bytes] = set()
    last_checked_era = -1

    for expr_id in exprs:
        value = None
        try:
            from astreum.consensus.constants import STORAGE_ADDRESS
            storage_account = None
            if hasattr(latest_block, "accounts"):
                storage_account = latest_block.accounts.get_account(STORAGE_ADDRESS, node)
            if storage_account is not None:
                value = get_from_radix_tree(storage_account.data, node, expr_id)
        except Exception:
            value = None

        if value is None:
            node.logger.debug("Cold-storage recovery: orphan %s skipped", expr_id.hex())
        else:
            _recover_one(node, expr_id, value, records_held)

        # Era check — the claim pass runs whenever the era rolls over so
        # recovery and claiming interleave in the same thread.
        current_era = latest_block.height // ERA_SIZE
        if current_era != last_checked_era:
            claims = _build_claims_for_records(
                node, latest_block, records_held, spacing_eras
            )
            _submit_claims(node, claims)
            last_checked_era = current_era

    node.storage_records_held = records_held
    node.logger.info(
        "Cold-storage recovery complete: %d record(s) held, %d slot(s) registered",
        len(records_held),
        len(node.storage_slot_registry),
    )
    return last_checked_era


def claim_storage(node: Node) -> None:
    """Submit storage reward claims on era boundaries.

    Runs as a daemon thread.  On each era boundary (every
    ``ERA_SIZE`` blocks) it evaluates the records this node holds
    (``storage_records_held``, rebuilt from cold storage at boot) where
    this node is a provider, computes a proof-of-work challenge for each
    eligible slot, and submits a single ``STORAGE_PAYMENT`` transaction
    bundling all claims.

    A one-shot cold-boot recovery runs first (after the ``latest_block``
    wait), rebuilding ``storage_slot_registry`` + ``storage_records_held`` +
    ``expr_advertisements`` from cold storage and interleaving claims at era
    boundaries before falling back to the era-boundary claim loop.

    Claim spacing uses a progressive back-off when incumbent
    (``claim_spacing_eras``, 1→4 eras) and a wall-drop threshold of
    5 eras for non-incumbent takeover attempts.

    Args:
        node: A fully initialized Node instance with ``storage_records_held``,
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
    if not hasattr(node, "storage_records_held"):
        node.storage_records_held = set()

    while not stop.is_set():
        latest_block = getattr(node, "latest_block", None)
        if latest_block is None:
            stop.wait(1.0)
            continue

        if not getattr(node, "_cold_recovery_done", False):
            try:
                last_checked_era = _run_cold_recovery(node)
            except Exception as exc:
                node.logger.exception("Cold-storage recovery failed: %s", exc)
            finally:
                node._cold_recovery_done = True
            if stop.is_set():
                return

        current_era = latest_block.height // ERA_SIZE
        if current_era == last_checked_era:
            # Wait until next era boundary
            next_boundary = (current_era + 1) * ERA_SIZE
            blocks_remaining = next_boundary - latest_block.height
            wait_seconds = max(1.0, blocks_remaining * 0.5)
            stop.wait(wait_seconds)
            continue

        # Era changed — evaluate all held records
        claims_to_make = _build_claims_for_records(
            node,
            latest_block,
            node.storage_records_held,
            node.claim_spacing_eras,
        )
        _submit_claims(node, claims_to_make)

        last_checked_era = current_era
        stop.wait(0.5)
