from __future__ import annotations

import math
import time
from queue import Empty
from typing import Any, Callable

from ...consensus.account import create_account
from ...machine.models.expression import Expr, link_list_to_expr, resolve_inner_exprs, resolve_list_exprs
from ...storage.actions.set import _hot_storage_set
from ..models.block import Block
from ...consensus.transaction import Transaction, apply_transaction
from ..constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..validator import current_validator
from ...machine.models.expression import ZERO32
from ...communication.object_response.object_found import OBJECT_FOUND_LIST_PAYLOAD
from ...storage.advertisments import advertise_exprs
from ...communication.models.message import Message, MessageTopic
from ...communication.models.ping import Ping
from ...communication.difficulty import message_difficulty
from ...communication.outgoing_queue import enqueue_outgoing
from ...storage.cold.insert import insert_expr_into_cold_storage

validator_advertisment_limit_seconds = 15 * 60


def _collect_block_ads(node: Any, block: Block) -> list[bytes]:
    heads: list[bytes] = []
    if block.atom_hash and block.atom_hash != ZERO32:
        heads.append(block.atom_hash)
    if block.body_hash and block.body_hash != ZERO32:
        body_expr = node.get_expr(block.body_hash)
        if body_expr is not None:
            heads.append(block.body_hash)
    return heads


def _collect_transaction_ads(node: Any, transactions: list[Transaction]) -> list[bytes]:
    ads: list[bytes] = []
    for tx in transactions:
        if not tx.hash:
            continue
        ads.append(tx.hash)
        tx_header = node.get_expr_list(tx.hash)
        if tx_header is not None:
            header_nodes, _ = resolve_list_exprs(node, tx_header)
            if len(header_nodes) >= 4:
                body_node = header_nodes[0]
                if isinstance(body_node, Expr.Link) and body_node.hash() != ZERO32:
                    ads.append(body_node.hash())
    return ads


def _collect_receipt_ads(receipt_ids: list[bytes]) -> list[bytes]:
    return [rid for rid in receipt_ids if rid and rid != ZERO32]


def _collect_account_ads(accounts_hash: bytes | None, account_exprs: list[Expr]) -> list[bytes]:
    ads: list[bytes] = []
    if accounts_hash and accounts_hash != ZERO32:
        ads.append(accounts_hash)
    for expr in account_exprs:
        if isinstance(expr, Expr.Symbol) and expr.value == "trie":
            ads.append(expr.hash())
    return ads


def make_validation_worker(
    node: Any,
) -> Callable[[], None]:
    """Build the validation worker bound to the given node."""

    def _validation_worker() -> None:
        node.logger.info("Validation worker started")
        stop = node._validation_stop_event

        def _award_validator_reward(block: Block, reward_amount: int) -> None:
            """Credit the validator account with the provided reward."""
            if reward_amount <= 0:
                return
            accounts = getattr(block, "accounts", None)
            validator_key = getattr(block, "validator_public_key_bytes", None)
            if accounts is None or not validator_key:
                node.logger.debug(
                    "Skipping validator reward; accounts snapshot or key missing"
                )
                return
            try:
                validator_account = accounts.get_account(
                    address=validator_key, node=node
                )
            except Exception:
                node.logger.exception("Unable to load validator account for reward")
                return
            if validator_account is None:
                validator_account = create_account()
            validator_account.balance += reward_amount
            accounts.set_account(validator_key, validator_account)

        while not stop.is_set():
            validation_public_key = node.config.get("validation_public_key_bytes")
            
            if not validation_public_key:
                node.logger.debug("Validation public key unavailable; sleeping")
                time.sleep(0.5)
                continue

            latest_block_hash = node.latest_block_hash
            if latest_block_hash is None:
                node.logger.warning("Missing latest_block_hash; retrying")
                time.sleep(0.5)
                continue

            node.logger.debug(
                "Querying current validator for block %s",
                latest_block_hash,
            )
            
            try:
                scheduled_validator, accounts_snapshot = current_validator(node, latest_block_hash)
            except Exception as exc:
                node.logger.exception("Unable to determine current validator: %s", exc)
                time.sleep(0.5)
                continue

            if scheduled_validator != validation_public_key:
                expected_hex = (
                    scheduled_validator.hex()
                    if isinstance(scheduled_validator, (bytes, bytearray))
                    else scheduled_validator
                )
                node.logger.debug("Current validator mismatch; expected %s", expected_hex)
                time.sleep(0.5)
                continue

            try:
                previous_block = Block.from_storage(node, latest_block_hash)
            except Exception:
                node.logger.exception("Unable to load previous block for validation")
                time.sleep(0.5)
                continue

            try:
                current_hash = node._validation_transaction_queue.get_nowait()
                queue_empty = False
            except Empty:
                current_hash = None
                queue_empty = True
                node.logger.debug(
                    "No pending validation transactions; generating empty block"
                )

            new_block = Block(
                chain_id=getattr(node, "chain", 0),
                previous_block_hash=latest_block_hash,
                previous_block=previous_block,
                height=(previous_block.height or 0) + 1,
                timestamp=None,
                accounts_hash=previous_block.accounts_hash,
                total_transaction_fee=0,
                total_storage_fee=0,
                cumulative_transaction_fee=0,
                cumulative_storage_fee=0,
                cumulative_stake=0,
                cumulative_burn=0,
                cumulative_mint=0,
                transactions_hash=None,
                receipts_hash=None,
                difficulty=None,
                validator_public_key_bytes=validation_public_key,
                nonce=0,
                signature=None,
                accounts=accounts_snapshot,
                transactions=[],
                receipts=[],
            )
            node.logger.debug(
                "Creating block #%s extending %s",
                new_block.height,
                node.latest_block_hash,
            )

            # we may want to add a timer to process part of the txs only on a slow computer
            new_block.transactions = new_block.transactions or []
            new_block.receipts = new_block.receipts or []
            total_transaction_fee = 0
            total_storage_fee = 0
            total_fee = 0
            while current_hash is not None:
                try:
                    tx_fee, storage_fee, combined_fee = apply_transaction(node, new_block, current_hash)
                    total_transaction_fee += int(tx_fee)
                    total_storage_fee += int(storage_fee)
                    total_fee += int(combined_fee)
                except NotImplementedError:
                    tx_hex = current_hash
                    node.logger.warning("Transaction %s unsupported; re-queued", tx_hex)
                    node._validation_transaction_queue.put(current_hash)
                    time.sleep(0.5)
                    break
                except Exception:
                    tx_hex = current_hash
                    node.logger.exception("Failed applying transaction %s", tx_hex)

                try:
                    current_hash = node._validation_transaction_queue.get_nowait()
                except Empty:
                    current_hash = None

            # Adaptive block spacing
            if total_fee > 0:
                node.block_spacing = 2
            else:
                node.block_spacing += 1

            new_block.total_transaction_fee = total_transaction_fee
            new_block.total_storage_fee = total_storage_fee
            new_block.cumulative_transaction_fee = previous_block.cumulative_transaction_fee + int(total_transaction_fee)
            new_block.cumulative_storage_fee = previous_block.cumulative_storage_fee + int(total_storage_fee)
            new_block.cumulative_mint = previous_block.cumulative_mint + new_block.total_mint

            treasury_account = new_block.accounts.get_account(TREASURY_ADDRESS, node)
            burn_account = new_block.accounts.get_account(BURN_ADDRESS, node)
            new_block.cumulative_stake = previous_block.cumulative_stake + treasury_account.balance
            new_block.cumulative_burn = previous_block.cumulative_burn + burn_account.balance
            reward_amount = total_fee if total_fee > 0 else 1
            if total_fee == 0 and queue_empty:
                node.logger.debug("Awarding base validator reward of 1 aster")
            elif total_fee > 0:
                node.logger.debug(
                    "Collected %d aster in total fees for this block (tx=%d storage=%d)",
                    total_fee,
                    total_transaction_fee,
                    total_storage_fee,
                )
            _award_validator_reward(new_block, reward_amount)

            # create an atom list of transactions, save the list head hash as the block's transactions_hash
            transactions = new_block.transactions or []
            tx_hashes = [bytes(tx.hash) for tx in transactions if tx.hash]
            head_hash = link_list_to_expr(tx_hashes).hash()
            new_block.transactions_hash = head_hash
            node.logger.debug("Block includes %d transactions", len(transactions))
            transaction_atoms = []
            for tx in transactions:
                if not tx.hash:
                    continue
                tx_exprs, _ = resolve_inner_exprs(node, tx.expr())
                transaction_atoms.extend(tx_exprs)
            pending_exprs = list(new_block.pending_exprs)

            receipts = new_block.receipts or []
            receipt_atoms = []
            receipt_hashes = []
            for rcpt in receipts:
                receipt_id = rcpt.expr().hash()
                receipt_exprs, _ = resolve_inner_exprs(node, rcpt.expr())
                receipt_atoms.extend(receipt_exprs)
                receipt_hashes.append(bytes(receipt_id))
            receipts_head = link_list_to_expr(receipt_hashes).hash()
            new_block.receipts_hash = receipts_head
            node.logger.debug("Block includes %d receipts", len(receipts))

            account_exprs = []
            pending_account_exprs = []
            if new_block.accounts is not None:
                try:
                    pending_account_exprs = list(new_block.accounts.pending_exprs)
                    account_exprs = new_block.accounts.update_trie(node)
                    new_block.accounts_hash = new_block.accounts.root_hash
                    node.logger.debug(
                        "Updated trie for %d cached accounts",
                        len(new_block.accounts._cache),
                    )
                except Exception:
                    node.logger.exception("Failed to update accounts trie for block")

            now = time.time()
            spacing = node.block_spacing
            min_allowed = new_block.previous_block.timestamp + spacing
            nonce_time_seconds = node.nonce_time_ms / 1000.0
            expected_blocktime = now + nonce_time_seconds + spacing
            new_block.timestamp = max(int(math.ceil(expected_blocktime)), min_allowed)

            new_block.difficulty = Block.calculate_block_difficulty(
                previous_timestamp=previous_block.timestamp,
                current_timestamp=new_block.timestamp,
                previous_difficulty=previous_block.difficulty,
            )
            
            try:
                nonce_started = time.perf_counter()
                new_block.generate_nonce(difficulty=previous_block.difficulty)
                elapsed_ms = int((time.perf_counter() - nonce_started) * 1000)
                setattr(node, "nonce_time_ms", elapsed_ms)
                node.logger.debug(
                    "Found nonce %s for block #%s at difficulty %s",
                    new_block.nonce,
                    new_block.height,
                    new_block.difficulty,
                )
            except Exception:
                node.logger.exception("Failed while searching for block nonce")
                time.sleep(0.5)
                continue
            
            # wait until the block timestamp is reached before propagating
            now = time.time()
            if now > (new_block.timestamp + 2):
                node.logger.warning(
                    "Skipping block #%s propagation; timestamp %s already elapsed (now=%s)",
                    new_block.height,
                    new_block.timestamp,
                    now,
                )
                continue

            spread_delay = new_block.timestamp - now
            if spread_delay > 0:
                node.logger.debug(
                    "Delaying distribution for %.3fs to reach block timestamp %s",
                    spread_delay,
                    new_block.timestamp,
                )
                time.sleep(spread_delay)
                
            new_block_hash = new_block.expr().hash()
            block_exprs, _ = resolve_inner_exprs(node, new_block.expr())
            hot_store_failures = 0
            
            # hot set block exprs
            for block_expr in block_exprs:
                if not _hot_storage_set(node, block_expr):
                    hot_store_failures += 1

            # hot set receipt exprs
            for receipt_expr in receipt_atoms:
                if not _hot_storage_set(node, receipt_expr):
                    hot_store_failures += 1

            # hot set transaction exprs
            for transaction_atom in transaction_atoms:
                if not _hot_storage_set(node, transaction_atom):
                    hot_store_failures += 1

            # hot set pending exprs
            for pending_expr in pending_exprs:
                if not _hot_storage_set(node, pending_expr):
                    hot_store_failures += 1

            # hot set account exprs
            for account_expr in account_exprs:
                if not _hot_storage_set(node, account_expr):
                    hot_store_failures += 1

            if hot_store_failures:
                node.logger.warning(
                    "Block hot storage writes skipped for block #%s: count=%s",
                    new_block.height,
                    hot_store_failures,
                )

            expires_at = time.time() + validator_advertisment_limit_seconds
            advertisement_ids = []
            advertisement_ids.extend(_collect_block_ads(node, new_block))
            advertisement_ids.extend(_collect_transaction_ads(node, transactions))
            advertisement_ids.extend(_collect_receipt_ads(receipt_hashes))
            advertisement_ids.extend(_collect_account_ads(new_block.accounts_hash, account_exprs))
            advertisement_ids.extend(
                expr.hash() for expr in pending_exprs if expr.hash() != ZERO32
            )
            if advertisement_ids:
                entries = [
                    (atom_id, OBJECT_FOUND_LIST_PAYLOAD, expires_at)
                    for atom_id in advertisement_ids
                ]
                node.add_atom_advertisements(entries)
                advertised_ids, advertise_warning = advertise_exprs(node, entries=entries)
                if advertise_warning:
                    node.logger.warning(
                        "Block advertisement batch had failures for block #%s: advertised=%s reason=%s",
                        new_block.height,
                        len(advertised_ids),
                        advertise_warning,
                    )
            # put as own latest block hash
            node.latest_block_hash = new_block_hash
            node.latest_block = new_block
            node.logger.info(
                "Created block #%s with hash %s (%d nodes)",
                new_block.height,
                new_block_hash.hex(),
                len(block_exprs),
            )
            

            # ping all peers to update their records
            if node.outgoing_queue and node.peers:
                try:
                    with node.peers_lock:
                        peers = list(node.peers.items())
                except Exception:
                    peers = list(node.peers.items())

                if peers:
                    ping_payload = Ping(
                        is_validator=True,
                        difficulty=message_difficulty(node),
                        latest_block=new_block_hash,
                    ).to_bytes()

                    for peer_key, peer in peers:
                        peer_hex = (
                            peer_key.hex()
                            if isinstance(peer_key, (bytes, bytearray))
                            else peer_key
                        )
                        address = getattr(peer, "address", None)
                        if not address:
                            node.logger.debug(
                                "Skipping validator ping to %s; address missing",
                                peer_hex,
                            )
                            continue
                        try:
                            ping_msg = Message(
                                topic=MessageTopic.PING,
                                content=ping_payload,
                                sender=node.relay_public_key,
                            )
                            ping_msg.encrypt(peer.shared_key_bytes)
                            if enqueue_outgoing(
                                node,
                                address,
                                message=ping_msg,
                                difficulty=peer.difficulty,
                            ):
                                node.logger.debug(
                                    "Queued validator ping to %s (%s)",
                                    address,
                                    peer_key.hex()
                                    if isinstance(peer_key, (bytes, bytearray))
                                    else peer_key,
                                )
                            else:
                                node.logger.debug(
                                    "Dropped validator ping to %s (%s); enqueue rejected",
                                    address,
                                    peer_key.hex()
                                    if isinstance(peer_key, (bytes, bytearray))
                                    else peer_key,
                                )
                        except Exception:
                            node.logger.exception("Failed queueing validator ping to %s", address)

            # upload block nodes
            for block_expr in block_exprs:
                insert_expr_into_cold_storage(node, block_expr)

            # upload receipt exprs
            for receipt_expr in receipt_atoms:
                insert_expr_into_cold_storage(node, receipt_expr)

            # upload transaction atoms
            for transaction_atom in transaction_atoms:
                insert_atom_into_cold_storage(node, transaction_atom)

            # upload pending exprs
            for pending_expr in pending_exprs:
                insert_expr_into_cold_storage(node, pending_expr)

            # upload account exprs
            for account_expr in account_exprs:
                insert_expr_into_cold_storage(node, account_expr)
            if new_block.accounts is not None:
                for account_expr in pending_account_exprs:
                    if account_expr in new_block.accounts.pending_exprs:
                        new_block.accounts.pending_exprs.remove(account_expr)

        node.logger.info("Validation worker stopped")

    return _validation_worker
