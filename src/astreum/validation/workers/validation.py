from __future__ import annotations

import math
import time
from queue import Empty
from typing import Any, Callable

from ..models.account import Account
from ..models.accounts import Accounts
from ..models.block import Block
from ..models.transaction import Transaction, apply_transaction
from ..constants import TREASURY_ADDRESS
from ..validator import current_validator
from ...storage.models.atom import Atom, AtomKind, ZERO32, bytes_list_to_atoms
from ...communication.handlers.object_response import OBJECT_FOUND_LIST_PAYLOAD
from ...storage.advertisments import advertise_atoms
from ...communication.models.message import Message, MessageTopic
from ...communication.models.ping import Ping
from ...communication.difficulty import message_difficulty
from ...communication.outgoing_queue import enqueue_outgoing
from ...storage.cold.insert import insert_atom_into_cold_storage

validator_advertisment_limit_seconds = 15 * 60


def _collect_block_ads(node: Any, block: Block) -> list[bytes]:
    heads: list[bytes] = []
    if block.atom_hash and block.atom_hash != ZERO32:
        heads.append(block.atom_hash)
    if block.body_hash and block.body_hash != ZERO32:
        body_list_atom = node.get_atom_from_local_storage(block.body_hash)
        if body_list_atom and body_list_atom.data and body_list_atom.data != ZERO32:
            heads.append(body_list_atom.data)
    return heads


def _collect_transaction_ads(node: Any, transactions: list[Transaction]) -> list[bytes]:
    ads: list[bytes] = []
    for tx in transactions:
        if not tx.hash:
            continue
        ads.append(tx.hash)
        tx_chain = node.get_atom_list(tx.hash)
        if tx_chain:
            body_list_atom: Atom = tx_chain[-1]
            if (
                body_list_atom.kind is AtomKind.LIST
                and body_list_atom.data
                and body_list_atom.data != ZERO32
            ):
                ads.append(body_list_atom.data)
    return ads


def _collect_receipt_ads(receipt_ids: list[bytes]) -> list[bytes]:
    return [rid for rid in receipt_ids if rid and rid != ZERO32]


def _collect_account_ads(accounts_hash: bytes | None, account_atoms: list[Atom]) -> list[bytes]:
    ads: list[bytes] = []
    if accounts_hash and accounts_hash != ZERO32:
        ads.append(accounts_hash)
    for atom in account_atoms:
        if atom.kind is AtomKind.SYMBOL and atom.data == b"trie":
            ads.append(atom.object_id())
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
                validator_account = Account.create()
            validator_account.balance += reward_amount
            accounts.set_account(validator_key, validator_account)

        while not stop.is_set():
            validation_public_key = getattr(node, "validation_public_key", None)
            if not validation_public_key:
                node.logger.debug("Validation public key unavailable; sleeping")
                time.sleep(0.5)
                continue

            latest_block_hash = getattr(node, "latest_block_hash", None)
            if not isinstance(latest_block_hash, (bytes, bytearray)):
                node.logger.warning("Missing latest_block_hash; retrying")
                time.sleep(0.5)
                continue

            node.logger.debug(
                "Querying current validator for block %s",
                latest_block_hash.hex()
                if isinstance(latest_block_hash, (bytes, bytearray))
                else latest_block_hash,
            )
            try:
                scheduled_validator, _ = current_validator(node, latest_block_hash)
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

            try:
                accounts_snapshot = Accounts(root_hash=previous_block.accounts_hash)
            except Exception:
                accounts_snapshot = None
                node.logger.warning("Unable to initialise accounts snapshot for block")

            new_block = Block(
                chain_id=getattr(node, "chain", 0),
                previous_block_hash=latest_block_hash,
                previous_block=previous_block,
                height=(previous_block.height or 0) + 1,
                timestamp=None,
                accounts_hash=previous_block.accounts_hash,
                total_fees=0,
                cumulative_total_fees=0,
                cumulative_stake=0,
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
                (
                    node.latest_block_hash.hex()
                    if isinstance(node.latest_block_hash, (bytes, bytearray))
                    else node.latest_block_hash
                ),
            )

            # we may want to add a timer to process part of the txs only on a slow computer
            total_fees = 0
            while current_hash is not None:
                try:
                    total_fees += apply_transaction(node, new_block, current_hash)
                except NotImplementedError:
                    tx_hex = (
                        current_hash.hex()
                        if isinstance(current_hash, (bytes, bytearray))
                        else current_hash
                    )
                    node.logger.warning("Transaction %s unsupported; re-queued", tx_hex)
                    node._validation_transaction_queue.put(current_hash)
                    time.sleep(0.5)
                    break
                except Exception:
                    tx_hex = (
                        current_hash.hex()
                        if isinstance(current_hash, (bytes, bytearray))
                        else current_hash
                    )
                    node.logger.exception("Failed applying transaction %s", tx_hex)

                try:
                    current_hash = node._validation_transaction_queue.get_nowait()
                except Empty:
                    current_hash = None

            new_block.total_fees = total_fees
            new_block.cumulative_total_fees = previous_block.cumulative_total_fees + int(total_fees)

            treasury_balance = 0
            if new_block.accounts is not None:
                try:
                    treasury_account = new_block.accounts.get_account(TREASURY_ADDRESS, node)
                except Exception:
                    treasury_account = None
                if treasury_account is None:
                    node.logger.warning("Treasury account missing; defaulting stake balance to 0")
                else:
                    treasury_balance = int(treasury_account.balance or 0)

            new_block.cumulative_stake = previous_block.cumulative_stake + treasury_balance
            reward_amount = total_fees if total_fees > 0 else 1
            if total_fees == 0 and queue_empty:
                node.logger.debug("Awarding base validator reward of 1 aster")
            elif total_fees > 0:
                node.logger.debug(
                    "Collected %d aster in transaction fees for this block", total_fees
                )
            _award_validator_reward(new_block, reward_amount)

            # create an atom list of transactions, save the list head hash as the block's transactions_hash
            transactions = new_block.transactions or []
            tx_hashes = [bytes(tx.hash) for tx in transactions if tx.hash]
            head_hash, _ = bytes_list_to_atoms(tx_hashes)
            new_block.transactions_hash = head_hash
            node.logger.debug("Block includes %d transactions", len(transactions))
            transaction_atoms = []
            for tx in transactions:
                if not tx.hash:
                    continue
                atoms = Transaction.get_atoms(node, tx.hash)
                if atoms is None:
                    node.logger.debug(
                        "Unable to load transaction atoms for %s",
                        tx.hash.hex(),
                    )
                    continue
                transaction_atoms.extend(atoms)

            receipts = new_block.receipts or []
            receipt_atoms = []
            receipt_hashes = []
            for rcpt in receipts:
                receipt_id, atoms = rcpt.atomize()
                receipt_atoms.extend(atoms)
                receipt_hashes.append(bytes(receipt_id))
            receipts_head, _ = bytes_list_to_atoms(receipt_hashes)
            new_block.receipts_hash = receipts_head
            node.logger.debug("Block includes %d receipts", len(receipts))

            account_atoms = []
            if new_block.accounts is not None:
                try:
                    account_atoms = new_block.accounts.update_trie(node)
                    new_block.accounts_hash = new_block.accounts.root_hash
                    node.logger.debug(
                        "Updated trie for %d cached accounts",
                        len(new_block.accounts._cache),
                    )
                except Exception:
                    node.logger.exception("Failed to update accounts trie for block")

            now = time.time()
            min_allowed = new_block.previous_block.timestamp + 1
            nonce_time_seconds = node.nonce_time_ms / 1000.0
            expected_blocktime = now + nonce_time_seconds
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
                
            # atomize block
            new_block_hash, new_block_atoms = new_block.atomize()
            
            # hot set block atoms
            for block_atom in new_block_atoms:
                atom_id = block_atom.object_id()
                node._hot_storage_set(atom_id, block_atom)

            # hot set receipt atoms
            for receipt_atom in receipt_atoms:
                atom_id = receipt_atom.object_id()
                node._hot_storage_set(atom_id, receipt_atom)

            # hot set transaction atoms
            for transaction_atom in transaction_atoms:
                atom_id = transaction_atom.object_id()
                node._hot_storage_set(atom_id, transaction_atom)

            # hot set account atoms
            for account_atom in account_atoms:
                atom_id = account_atom.object_id()
                node._hot_storage_set(atom_id, account_atom)

            expires_at = time.time() + validator_advertisment_limit_seconds
            advertisement_ids = []
            advertisement_ids.extend(_collect_block_ads(node, new_block))
            advertisement_ids.extend(_collect_transaction_ads(node, transactions))
            advertisement_ids.extend(_collect_receipt_ads(receipt_hashes))
            advertisement_ids.extend(_collect_account_ads(new_block.accounts_hash, account_atoms))
            if advertisement_ids:
                entries = [
                    (atom_id, OBJECT_FOUND_LIST_PAYLOAD, expires_at)
                    for atom_id in advertisement_ids
                ]
                node.add_atom_advertisements(entries)
                advertise_atoms(node, entries=entries)
            # put as own latest block hash
            node.latest_block_hash = new_block_hash
            node.latest_block = new_block
            node.logger.info(
                "Created block #%s with hash %s (%d atoms)",
                new_block.height,
                new_block_hash.hex(),
                len(new_block_atoms),
            )
            

            # ping all peers to update their records
            if node.outgoing_queue and node.peers:
                try:
                    with node.peers_lock:
                        peers = list(node.peers.items())
                except Exception:
                    peers = list(getattr(node, "peers", {}).items())

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
                                    "Dropped validator ping to %s (%s); outgoing queue full",
                                    address,
                                    peer_key.hex()
                                    if isinstance(peer_key, (bytes, bytearray))
                                    else peer_key,
                                )
                        except Exception:
                            node.logger.exception("Failed queueing validator ping to %s", address)

            # upload block atoms
            for block_atom in new_block_atoms:
                insert_atom_into_cold_storage(node, block_atom)

            # upload receipt atoms
            for receipt_atom in receipt_atoms:
                insert_atom_into_cold_storage(node, receipt_atom)

            # upload transaction atoms
            for transaction_atom in transaction_atoms:
                insert_atom_into_cold_storage(node, transaction_atom)

            # upload account atoms
            for account_atom in account_atoms:
                insert_atom_into_cold_storage(node, account_atom)

        node.logger.info("Validation worker stopped")

    return _validation_worker
