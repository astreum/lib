from __future__ import annotations

import time
from queue import Empty
from typing import Any, Callable

from ..block import Block
from ..transaction import apply_transaction
from ..._storage.atom import bytes_list_to_atoms
from ..._storage.patricia import PatriciaTrie
from ..._communication.message import Message, MessageTopic
from ..._communication.ping import Ping


def make_validation_worker(
    node: Any,
    *,
    current_validator: Callable[[Any], bytes],
) -> Callable[[], None]:
    """Build the validation worker bound to the given node."""

    def _validation_worker() -> None:
        stop = node._validation_stop_event
        while not stop.is_set():
            validation_public_key = getattr(node, "validation_public_key", None)
            if not validation_public_key:
                time.sleep(0.5)
                continue

            scheduled_validator = current_validator(node)

            if scheduled_validator != validation_public_key:
                time.sleep(0.5)
                continue

            try:
                current_hash = node._validation_transaction_queue.get_nowait()
            except Empty:
                time.sleep(0.1)
                continue

            # create thread to perform vdf

            new_block = Block()
            new_block.validator_public_key = validation_public_key
            new_block.previous_block_hash = node.latest_block_hash
            try:
                new_block.previous_block = Block.from_atom(node, new_block.previous_block_hash)
            except Exception:
                continue
            new_block.accounts = PatriciaTrie(root_hash=new_block.previous_block.accounts_hash)

            # we may want to add a timer to process part of the txs only on a slow computer
            while True:
                try:
                    apply_transaction(node, new_block, current_hash)
                except NotImplementedError:
                    node._validation_transaction_queue.put(current_hash)
                    time.sleep(0.5)
                    break
                except Exception:
                    pass

                try:
                    current_hash = node._validation_transaction_queue.get_nowait()
                except Empty:
                    break

            # create an atom list of transactions, save the list head hash as the block's transactions_hash
            transactions = new_block.transactions or []
            tx_hashes = [bytes(tx.hash) for tx in transactions if tx.hash]
            head_hash, _ = bytes_list_to_atoms(tx_hashes)
            new_block.transactions_hash = head_hash

            receipts = new_block.receipts or []
            receipt_hashes = [bytes(rcpt.hash) for rcpt in receipts if rcpt.hash]
            receipts_head, _ = bytes_list_to_atoms(receipt_hashes)
            new_block.receipts_hash = receipts_head

            # get vdf result, default to 0 for now

            # get timestamp or wait for a the next second from the previous block, rule is the next block must be atleast 1 second after the previous
            now = time.time()
            min_allowed = new_block.previous_block.timestamp + 1
            if now < min_allowed:
                time.sleep(max(0.0, min_allowed - now))
                now = time.time()
            new_block.timestamp = max(int(now), min_allowed)

            # atomize block
            new_block_hash, _ = new_block.to_atom()
            # put as own latest block hash
            node.latest_block_hash = new_block_hash

            # ping peers in the validation route to update there records
            if node.validation_route and node.outgoing_queue and node.addresses:
                route_peers = {
                    peer_key
                    for bucket in getattr(node.validation_route, "buckets", {}).values()
                    for peer_key in bucket
                }
                if route_peers:
                    ping_payload = Ping(
                        is_validator=True,
                        latest_block=new_block_hash,
                    ).to_bytes()

                    message_bytes = Message(
                        topic=MessageTopic.PING,
                        content=ping_payload,
                    ).to_bytes()

                    for address, peer_key in node.addresses.items():
                        if peer_key in route_peers:
                            try:
                                node.outgoing_queue.put((message_bytes, address))
                            except Exception:
                                pass

            # store the new block and receipts

    return _validation_worker
