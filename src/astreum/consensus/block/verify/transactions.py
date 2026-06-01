from __future__ import annotations

from typing import Any, List, Optional

from ....machine.models.expression import Expr, link_list_to_expr
from ....validation.models.accounts import Accounts

ZERO32 = b"\x00" * 32
from ....validation.models.receipt import Receipt
from ...transaction import apply_transaction
from ....validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ....crypto.bloom_tree import BloomTree
from ....crypto.bloom_search import make_search_variants, ERA_SIZE


def _hex(value: Optional[bytes]) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return str(value)


def verify_block_transactions(node: Any, block: Any) -> tuple[bool, Optional[str]]:
    """Verify receipts, transactions, and accounts hashes for this block."""
    if node is None:
        raise ValueError("node required for block verification")

    node.logger.debug("Block verify start block=%s", _hex(block.expr_id))

    if block.transactions_hash is None:
        node.logger.debug(
            "Block verify missing transactions_hash block=%s",
            _hex(block.expr_id),
        )
        return False, "missing transactions_hash"
    if block.receipts_hash is None:
        node.logger.debug(
            "Block verify missing receipts_hash block=%s",
            _hex(block.expr_id),
        )
        return False, "missing receipts_hash"
    if block.accounts_hash is None:
        node.logger.debug(
            "Block verify missing accounts_hash block=%s",
            _hex(block.expr_id),
        )
        return False, "missing accounts_hash"

    def _load_hash_list(head: bytes) -> Optional[List[bytes]]:
        if head == ZERO32:
            return []
        expr = node.get_expr_list(head)
        if expr is None:
            node.logger.debug(
                "Block verify missing list expr head=%s block=%s",
                _hex(head),
                _hex(block.expr_id),
            )
            return None
        result = []
        current = expr
        while isinstance(current, Expr.Link):
            if current.head_hash is None:
                node.logger.debug(
                    "Block verify list node missing head_hash head=%s block=%s",
                    _hex(head),
                    _hex(block.expr_id),
                )
                return None
            result.append(current.head_hash)
            current = current.tail
        return result

    prev_hash = block.previous_block_hash or ZERO32
    if prev_hash == ZERO32:
        if block.transactions_hash != ZERO32:
            node.logger.debug(
                "Block verify genesis tx hash mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis tx hash mismatch"
        if block.receipts_hash != ZERO32:
            node.logger.debug(
                "Block verify genesis receipts hash mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis receipts hash mismatch"
        if block.total_transaction_fee not in (0, None):
            node.logger.debug(
                "Block verify genesis total transaction fee mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis total transaction fee mismatch"
        if block.total_storage_fee not in (0, None):
            node.logger.debug(
                "Block verify genesis total storage fee mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis total storage fee mismatch"
        if int(block.total_fee) != 0:
            node.logger.debug(
                "Block verify genesis total fee mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis total fee mismatch"
        if int(block.cumulative_transaction_fee or 0) != 1:
            node.logger.debug(
                "Block verify genesis cumulative transaction fee mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis cumulative transaction fee mismatch"
        if int(block.cumulative_storage_fee or 0) != 0:
            node.logger.debug(
                "Block verify genesis cumulative storage fee mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis cumulative storage fee mismatch"
        if int(block.cumulative_mint or 0) != 0:
            node.logger.debug(
                "Block verify genesis cumulative mint mismatch block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis cumulative mint mismatch"
        if block.accounts_hash is None:
            node.logger.debug(
                "Block verify genesis missing accounts hash block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis missing accounts hash"
        genesis_accounts = Accounts(root_hash=block.accounts_hash)
        treasury_account = genesis_accounts.get_account(TREASURY_ADDRESS, node)
        if treasury_account is None:
            node.logger.debug(
                "Block verify genesis missing treasury account block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis missing treasury account"
        burn_account = genesis_accounts.get_account(BURN_ADDRESS, node)
        if burn_account is None:
            node.logger.debug(
                "Block verify genesis missing burn account block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis missing burn account"
        expected_genesis_stake = int(treasury_account.balance or 0)
        expected_genesis_burn = int(burn_account.balance or 0)
        if block.cumulative_stake is None:
            node.logger.debug(
                "Block verify genesis missing cumulative stake block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis missing cumulative stake"
        if int(block.cumulative_stake) != expected_genesis_stake:
            node.logger.debug(
                "Block verify genesis cumulative stake mismatch block=%s expected=%s actual=%s",
                _hex(block.expr_id),
                expected_genesis_stake,
                block.cumulative_stake,
            )
            return False, "genesis cumulative stake mismatch"
        if block.cumulative_burn is None:
            node.logger.debug(
                "Block verify genesis missing cumulative burn block=%s",
                _hex(block.expr_id),
            )
            return False, "genesis missing cumulative burn"
        if int(block.cumulative_burn) != expected_genesis_burn:
            node.logger.debug(
                "Block verify genesis cumulative burn mismatch block=%s expected=%s actual=%s",
                _hex(block.expr_id),
                expected_genesis_burn,
                block.cumulative_burn,
            )
            return False, "genesis cumulative burn mismatch"
        node.logger.debug("Block verify genesis passed block=%s", _hex(block.expr_id))
        return True, None

    prev_block = block.previous_block
    if prev_block is None:
        node.logger.debug(
            "Block verify failed loading parent block=%s prev=%s",
            _hex(block.expr_id),
            _hex(prev_hash),
        )
        return False, "failed loading parent block"

    if not prev_block.accounts_hash:
        node.logger.debug(
            "Block verify missing parent accounts hash block=%s",
            _hex(block.expr_id),
        )
        return False, "missing parent accounts hash"

    tx_hashes = _load_hash_list(block.transactions_hash)
    if tx_hashes is None:
        return False, "failed loading tx list"

    expected_tx_head = link_list_to_expr(tx_hashes).hash()
    if expected_tx_head != (block.transactions_hash or ZERO32):
        node.logger.debug(
            "Block verify tx head mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            _hex(expected_tx_head),
            _hex(block.transactions_hash),
        )
        return False, "tx head mismatch"

    accounts_snapshot = Accounts(root_hash=prev_block.accounts_hash)
    work_block = type("_WorkBlock", (), {})()
    work_block.chain_id = block.chain_id
    work_block.previous_block_hash = block.previous_block_hash
    work_block.previous_block = prev_block
    work_block.accounts = accounts_snapshot
    work_block.transactions = []
    work_block.receipts = []
    work_block.total_mint = 0

    total_transaction_fee = 0
    total_storage_fee = 0
    total_fee = 0

    # Bloom verification
    era_offset = block.height % ERA_SIZE
    if era_offset == 0 and block.height > 0:
        if prev_block is None:
            return False, "era boundary missing previous block"
        if block.previous_era_hash != prev_block.expr_id:
            return False, "era boundary previous_era_hash mismatch"
        bloom_era = BloomTree()
    else:
        bloom_era = prev_block.bloom_tree

    for tx_hash in tx_hashes:
        try:
            tx_fee, storage_fee, combined_fee = apply_transaction(node, work_block, tx_hash)
            total_transaction_fee += int(tx_fee)
            total_storage_fee += int(storage_fee)
            total_fee += int(combined_fee)

            # Insert bloom variants for this tx
            tx = None
            for applied in (work_block.transactions or []):
                if getattr(applied, "hash", None) == tx_hash:
                    tx = applied
                    break
            if tx:
                variants = make_search_variants(tx.hash, tx.sender, tx.recipient)
                bloom_era.insert(era_offset, variants, node)

        except Exception as exc:
            node.logger.debug(
                "Block verify failed applying tx=%s block=%s error=%s",
                _hex(tx_hash),
                _hex(block.expr_id),
                exc,
            )
            return False, f"failed applying tx={_hex(tx_hash)}"

    # Fill previous leaf and compare bloom hash
    if era_offset > 0 and prev_block is not None:
        bloom_era.set_leaf_start_hash(era_offset - 1, prev_block.expr_id)
    expected_bloom = bloom_era.root.expr().hash() if bloom_era.root else ZERO32
    if block.bloom_hash != expected_bloom:
        node.logger.debug(
            "Block verify bloom hash mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id), _hex(expected_bloom), _hex(block.bloom_hash),
        )
        return False, "bloom hash mismatch"

    if block.total_transaction_fee is None:
        node.logger.debug(
            "Block verify missing total transaction fee block=%s",
            _hex(block.expr_id),
        )
        return False, "missing total transaction fee"
    if int(block.total_transaction_fee) != int(total_transaction_fee):
        node.logger.debug(
            "Block verify total transaction fee mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            total_transaction_fee,
            block.total_transaction_fee,
        )
        return False, "total transaction fee mismatch"
    if block.total_storage_fee is None:
        node.logger.debug(
            "Block verify missing total storage fee block=%s",
            _hex(block.expr_id),
        )
        return False, "missing total storage fee"
    if int(block.total_storage_fee) != int(total_storage_fee):
        node.logger.debug(
            "Block verify total storage fee mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            total_storage_fee,
            block.total_storage_fee,
        )
        return False, "total storage fee mismatch"
    if int(block.total_fee) != int(total_fee):
        node.logger.debug(
            "Block verify total fee mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            total_fee,
            block.total_fee,
        )
        return False, "total fee mismatch"
    if block.cumulative_transaction_fee is None:
        node.logger.debug(
            "Block verify missing cumulative transaction fee block=%s",
            _hex(block.expr_id),
        )
        return False, "missing cumulative transaction fee"
    expected_cumulative_transaction_fee = int(prev_block.cumulative_transaction_fee) + int(total_transaction_fee)
    if int(block.cumulative_transaction_fee) != expected_cumulative_transaction_fee:
        node.logger.debug(
            "Block verify cumulative transaction fee mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            expected_cumulative_transaction_fee,
            block.cumulative_transaction_fee,
        )
        return False, "cumulative transaction fee mismatch"
    if block.cumulative_storage_fee is None:
        node.logger.debug(
            "Block verify missing cumulative storage fee block=%s",
            _hex(block.expr_id),
        )
        return False, "missing cumulative storage fee"
    expected_cumulative_storage_fee = int(prev_block.cumulative_storage_fee) + int(total_storage_fee)
    if int(block.cumulative_storage_fee) != expected_cumulative_storage_fee:
        node.logger.debug(
            "Block verify cumulative storage fee mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            expected_cumulative_storage_fee,
            block.cumulative_storage_fee,
        )
        return False, "cumulative storage fee mismatch"
    if block.cumulative_mint is None:
        node.logger.debug(
            "Block verify missing cumulative mint block=%s",
            _hex(block.expr_id),
        )
        return False, "missing cumulative mint"
    expected_cumulative_mint = prev_block.cumulative_mint + int(getattr(work_block, "total_mint", 0) or 0)
    if int(block.cumulative_mint) != expected_cumulative_mint:
        node.logger.debug(
            "Block verify cumulative mint mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            expected_cumulative_mint,
            block.cumulative_mint,
        )
        return False, "cumulative mint mismatch"

    applied_transactions = list(work_block.transactions or [])
    if len(applied_transactions) != len(tx_hashes):
        node.logger.debug(
            "Block verify tx count mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            len(tx_hashes),
            len(applied_transactions),
        )
        return False, "tx count mismatch"

    expected_receipts: List[Receipt] = list(work_block.receipts or [])
    if len(expected_receipts) != len(applied_transactions):
        node.logger.debug(
            "Block verify receipt count mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            len(applied_transactions),
            len(expected_receipts),
        )
        return False, "receipt count mismatch"
    expected_receipt_ids: List[bytes] = []
    for receipt in expected_receipts:
        receipt_id = receipt.expr().hash()
        expected_receipt_ids.append(receipt_id)

    expected_receipts_head = link_list_to_expr(expected_receipt_ids).hash()
    if expected_receipts_head != (block.receipts_hash or ZERO32):
        node.logger.debug(
            "Block verify receipts head mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            _hex(expected_receipts_head),
            _hex(block.receipts_hash),
        )
        return False, "receipts head mismatch"

    stored_receipt_ids = _load_hash_list(block.receipts_hash)
    if stored_receipt_ids is None:
        return False, "failed loading receipts list"
    if stored_receipt_ids != expected_receipt_ids:
        node.logger.debug(
            "Block verify receipts list mismatch block=%s",
            _hex(block.expr_id),
        )
        return False, "receipts list mismatch"
    for expected, stored_id in zip(expected_receipts, stored_receipt_ids):
        try:
            stored = Receipt.from_storage(node, stored_id)
        except Exception as exc:
            node.logger.debug(
                "Block verify failed loading receipt=%s block=%s error=%s",
                _hex(stored_id),
                _hex(block.expr_id),
                exc,
            )
            return False, f"failed loading receipt={_hex(stored_id)}"
        if stored.transaction_hash != expected.transaction_hash:
            node.logger.debug(
                "Block verify receipt tx mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt tx mismatch receipt={_hex(stored_id)}"
        if stored.status != expected.status:
            node.logger.debug(
                "Block verify receipt status mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt status mismatch receipt={_hex(stored_id)}"
        if stored.transaction_fee != expected.transaction_fee:
            node.logger.debug(
                "Block verify receipt transaction fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt transaction fee mismatch receipt={_hex(stored_id)}"
        if stored.storage_fee != expected.storage_fee:
            node.logger.debug(
                "Block verify receipt storage fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt storage fee mismatch receipt={_hex(stored_id)}"
        if stored.total_fee != expected.total_fee:
            node.logger.debug(
                "Block verify receipt total fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt total fee mismatch receipt={_hex(stored_id)}"
        if stored.logs_hash != expected.logs_hash:
            node.logger.debug(
                "Block verify receipt logs hash mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.expr_id),
            )
            return False, f"receipt logs hash mismatch receipt={_hex(stored_id)}"

    try:
        accounts_snapshot.update_trie(node)
    except Exception as exc:
        node.logger.debug(
            "Block verify failed updating accounts trie block=%s error=%s",
            _hex(block.expr_id),
            exc,
        )
        return False, "failed updating accounts trie"
    if accounts_snapshot.root_hash != block.accounts_hash:
        node.logger.debug(
            "Block verify accounts hash mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            _hex(accounts_snapshot.root_hash),
            _hex(block.accounts_hash),
        )
        return False, "accounts hash mismatch"
    treasury_account = accounts_snapshot.get_account(TREASURY_ADDRESS, node)
    if treasury_account is None:
        node.logger.debug(
            "Block verify missing treasury account block=%s",
            _hex(block.expr_id),
        )
        return False, "missing treasury account"
    treasury_balance = int(treasury_account.balance or 0)
    burn_account = accounts_snapshot.get_account(BURN_ADDRESS, node)
    if burn_account is None:
        node.logger.debug(
            "Block verify missing burn account block=%s",
            _hex(block.expr_id),
        )
        return False, "missing burn account"
    burn_balance = int(burn_account.balance or 0)
    if block.cumulative_stake is None:
        node.logger.debug(
            "Block verify missing cumulative stake block=%s",
            _hex(block.expr_id),
        )
        return False, "missing cumulative stake"
    expected_cumulative_stake = prev_block.cumulative_stake + treasury_balance
    if int(block.cumulative_stake) != expected_cumulative_stake:
        node.logger.debug(
            "Block verify cumulative stake mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            expected_cumulative_stake,
            block.cumulative_stake,
        )
        return False, "cumulative stake mismatch"
    if block.cumulative_burn is None:
        node.logger.debug(
            "Block verify missing cumulative burn block=%s",
            _hex(block.expr_id),
        )
        return False, "missing cumulative burn"
    expected_cumulative_burn = prev_block.cumulative_burn + burn_balance
    if int(block.cumulative_burn) != expected_cumulative_burn:
        node.logger.debug(
            "Block verify cumulative burn mismatch block=%s expected=%s actual=%s",
            _hex(block.expr_id),
            expected_cumulative_burn,
            block.cumulative_burn,
        )
        return False, "cumulative burn mismatch"

    node.logger.debug("Block verify success block=%s", _hex(block.expr_id))
    return True, None
