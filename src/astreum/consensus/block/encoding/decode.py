from __future__ import annotations

from typing import Any

from astreum.expression import Expr, resolve_list_exprs, ZERO32
from astreum.storage.get.list import get_expr_list
from astreum.consensus.models.block import Block
from astreum.consensus.block.create import create_block
from astreum.crypto.bloom_tree import BloomTree


def get_block_from_storage(astreum_node: Any, block_hash: bytes) -> Block:
    """Deserialize a Block from its S-expression stored at the given hash.

    Fetches and resolves the block header expression chain from storage
    and reconstructs a Block from it, including its bloom tree.

    Args:
        astreum_node: A Node instance for fetching expressions from storage.
        block_hash: The content hash of the serialized block.

    Returns:
        The deserialized Block.

    Raises:
        ValueError: If the block header cannot be fetched or parsed.
    """
    header = get_expr_list(astreum_node, block_hash)
    if header is None:
        raise ValueError("unable to load block header from storage")
    if not header._tag == "link":
        raise ValueError("block header must be a Link")
    if header._tail is None or header._tail._tag != "symbol" or header._tail.value != "block":
        raise ValueError(
            f"invalid block type tag (got {header._tail!r})"
        )

    inner = header._head
    if inner is None or inner._tag != "link":
        raise ValueError("block inner header must be a Link")

    inner_nodes, missed = resolve_list_exprs(astreum_node, inner)
    if missed:
        raise ValueError(
            f"unable to resolve block header (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(inner_nodes) != 2:
        raise ValueError(
            f"malformed block header length (got={len(inner_nodes)}, expected=2)"
        )

    body, sig = inner_nodes
    if not sig._tag == "bytes":
        raise ValueError("invalid block signature: expected Bytes")
    signature_bytes = sig.value
    if not body._tag == "link":
        raise ValueError("block body must be a Link chain")

    body_nodes, missed = resolve_list_exprs(astreum_node, body)
    if missed:
        raise ValueError(
            f"unable to resolve block body (missed={[h.hex()[:8] for h in missed]})"
        )
    if len(body_nodes) != 15:
        raise ValueError(
            f"malformed block body length (got={len(body_nodes)}, expected=15)"
        )

    (
        accounts_node,
        bloom_hash_node,
        chain_id_node,
        difficulty_node,
        height_node,
        nonce_node,
        prev_node,
        previous_era_hash_node,
        receipts_node,
        timestamp_node,
        total_storage_fee_node,
        total_transaction_fee_node,
        transactions_node,
        validator_node,
        statistics_node,
    ) = body_nodes

    if not accounts_node._tag == "link":
        raise ValueError("expected Link for accounts_hash")
    if not bloom_hash_node._tag == "link":
        raise ValueError("expected Link for bloom_hash")
    if not chain_id_node._tag == "int":
        raise ValueError("expected Int for chain_id")
    if not difficulty_node._tag == "int":
        raise ValueError("expected Int for difficulty")
    if not height_node._tag == "int":
        raise ValueError("expected Int for height")
    if not nonce_node._tag == "int":
        raise ValueError("expected Int for nonce")
    if not prev_node._tag == "link":
        raise ValueError("expected Link for previous_block_hash")
    if not previous_era_hash_node._tag == "link":
        raise ValueError("expected Link for previous_era_hash")
    if not receipts_node._tag == "link":
        raise ValueError("expected Link for receipts_hash")
    if not timestamp_node._tag == "int":
        raise ValueError("expected Int for timestamp")
    if not total_storage_fee_node._tag == "int":
        raise ValueError("expected Int for total_storage_fee")
    if not total_transaction_fee_node._tag == "int":
        raise ValueError("expected Int for total_transaction_fee")
    if not transactions_node._tag == "link":
        raise ValueError("expected Link for transactions_hash")
    if not validator_node._tag == "bytes":
        raise ValueError("expected Bytes for validator_public_key_bytes")

    if statistics_node._tag == "link":
        stat_nodes, missed = resolve_list_exprs(astreum_node, statistics_node)
        if missed:
            raise ValueError(
                f"unable to resolve statistics (missed={[h.hex()[:8] for h in missed]})"
            )
        statistics = []
        for j, entry_node in enumerate(stat_nodes):
            int_nodes, missed = resolve_list_exprs(astreum_node, entry_node)
            if missed:
                raise ValueError(
                    f"unable to resolve statistics entry {j} (missed={[h.hex()[:8] for h in missed]})"
                )
            if j == 0 and len(int_nodes) == 2:
                statistics.append((int_nodes[0].value, int_nodes[1].value, 0, 0))
            elif len(int_nodes) == 4:
                statistics.append((int_nodes[0].value, int_nodes[1].value, int_nodes[2].value, int_nodes[3].value))
            else:
                raise ValueError(
                    f"invalid statistics entry {j} length (got={len(int_nodes)})"
                )
    elif statistics_node._tag == "symbol":
        statistics = []
    else:
        raise ValueError("expected Link or Symbol for statistics")

    block = create_block(
        chain_id=chain_id_node.value,
        previous_block_hash=prev_node._head_hash if prev_node._head_hash is not None else ZERO32,
        previous_block=None,
        height=height_node.value,
        timestamp=timestamp_node.value,
        accounts_hash=accounts_node._head_hash or None,
        total_transaction_fee=total_transaction_fee_node.value,
        total_storage_fee=total_storage_fee_node.value,
        transactions_hash=transactions_node._head_hash or None,
        receipts_hash=receipts_node._head_hash or None,
        difficulty=difficulty_node.value,
        validator_public_key_bytes=validator_node.value or None,
        nonce=nonce_node.value,
        bloom_hash=bloom_hash_node._head_hash or None,
        previous_era_hash=previous_era_hash_node._head_hash or None,
        signature=signature_bytes,
        expr_id=block_hash,
        body_hash=body.hash(),
        statistics=statistics,
    )

    block.bloom_tree = BloomTree(block.bloom_hash, astreum_node)

    return block
