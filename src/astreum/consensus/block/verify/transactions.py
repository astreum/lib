from __future__ import annotations

from typing import Any, List, Optional

from ....storage.models.atom import AtomKind, ZERO32, bytes_list_to_atoms
from ....validation.models.accounts import Accounts
from ....validation.models.receipt import Receipt
from ...transaction import apply_transaction
from ....validation.constants import BURN_ADDRESS, TREASURY_ADDRESS


def _hex(value: Optional[bytes]) -> str:
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return str(value)


def verify_block_transactions(node: Any, block: Any) -> bool:
    """Verify receipts, transactions, and accounts hashes for this block."""
    if node is None:
        raise ValueError("node required for block verification")

    node.logger.debug("Block verify start block=%s", _hex(block.atom_hash))

    if block.transactions_hash is None:
        node.logger.warning("Block verify missing transactions_hash block=%s", _hex(block.atom_hash))
        return False
    if block.receipts_hash is None:
        node.logger.warning("Block verify missing receipts_hash block=%s", _hex(block.atom_hash))
        return False
    if block.accounts_hash is None:
        node.logger.warning("Block verify missing accounts_hash block=%s", _hex(block.atom_hash))
        return False

    def _load_hash_list(head: bytes) -> Optional[List[bytes]]:
        if head == ZERO32:
            return []
        atoms = node.get_atom_list(head)
        if atoms is None:
            node.logger.warning("Block verify missing list atoms head=%s block=%s", _hex(head), _hex(block.atom_hash))
            return None
        for atom in atoms:
            if atom.kind is not AtomKind.BYTES:
                node.logger.warning("Block verify list atom kind mismatch head=%s block=%s", _hex(head), _hex(block.atom_hash))
                return None
        return [bytes(atom.data) for atom in atoms]

    prev_hash = block.previous_block_hash or ZERO32
    if prev_hash == ZERO32:
        if block.transactions_hash != ZERO32:
            node.logger.warning("Block verify genesis tx hash mismatch block=%s", _hex(block.atom_hash))
            return False
        if block.receipts_hash != ZERO32:
            node.logger.warning("Block verify genesis receipts hash mismatch block=%s", _hex(block.atom_hash))
            return False
        if block.total_transaction_fee not in (0, None):
            node.logger.warning("Block verify genesis total transaction fee mismatch block=%s", _hex(block.atom_hash))
            return False
        if block.total_storage_fee not in (0, None):
            node.logger.warning("Block verify genesis total storage fee mismatch block=%s", _hex(block.atom_hash))
            return False
        if int(block.total_fee) != 0:
            node.logger.warning("Block verify genesis total fee mismatch block=%s", _hex(block.atom_hash))
            return False
        if int(block.cumulative_transaction_fee or 0) != 1:
            node.logger.warning("Block verify genesis cumulative transaction fee mismatch block=%s", _hex(block.atom_hash))
            return False
        if int(block.cumulative_storage_fee or 0) != 0:
            node.logger.warning("Block verify genesis cumulative storage fee mismatch block=%s", _hex(block.atom_hash))
            return False
        if int(block.cumulative_mint or 0) != 0:
            node.logger.warning("Block verify genesis cumulative mint mismatch block=%s", _hex(block.atom_hash))
            return False
        if block.accounts_hash is None:
            node.logger.warning("Block verify genesis missing accounts hash block=%s", _hex(block.atom_hash))
            return False
        genesis_accounts = Accounts(root_hash=block.accounts_hash)
        treasury_account = genesis_accounts.get_account(TREASURY_ADDRESS, node)
        if treasury_account is None:
            node.logger.warning("Block verify genesis missing treasury account block=%s", _hex(block.atom_hash))
            return False
        burn_account = genesis_accounts.get_account(BURN_ADDRESS, node)
        if burn_account is None:
            node.logger.warning("Block verify genesis missing burn account block=%s", _hex(block.atom_hash))
            return False
        expected_genesis_stake = int(treasury_account.balance or 0)
        expected_genesis_burn = int(burn_account.balance or 0)
        if block.cumulative_stake is None:
            node.logger.warning("Block verify genesis missing cumulative stake block=%s", _hex(block.atom_hash))
            return False
        if int(block.cumulative_stake) != expected_genesis_stake:
            node.logger.warning(
                "Block verify genesis cumulative stake mismatch block=%s expected=%s actual=%s",
                _hex(block.atom_hash),
                expected_genesis_stake,
                block.cumulative_stake,
            )
            return False
        if block.cumulative_burn is None:
            node.logger.warning("Block verify genesis missing cumulative burn block=%s", _hex(block.atom_hash))
            return False
        if int(block.cumulative_burn) != expected_genesis_burn:
            node.logger.warning(
                "Block verify genesis cumulative burn mismatch block=%s expected=%s actual=%s",
                _hex(block.atom_hash),
                expected_genesis_burn,
                block.cumulative_burn,
            )
            return False
        node.logger.debug("Block verify genesis passed block=%s", _hex(block.atom_hash))
        return True

    prev_block = block.previous_block
    if prev_block is None:
        node.logger.warning("Block verify failed loading parent block=%s prev=%s", _hex(block.atom_hash), _hex(prev_hash))
        return False

    if not prev_block.accounts_hash:
        node.logger.warning("Block verify missing parent accounts hash block=%s", _hex(block.atom_hash))
        return False

    tx_hashes = _load_hash_list(block.transactions_hash)
    if tx_hashes is None:
        node.logger.warning("Block verify failed loading tx list block=%s", _hex(block.atom_hash))
        return False

    expected_tx_head, _ = bytes_list_to_atoms(tx_hashes)
    if expected_tx_head != (block.transactions_hash or ZERO32):
        node.logger.warning(
            "Block verify tx head mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            _hex(expected_tx_head),
            _hex(block.transactions_hash),
        )
        return False

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
    for tx_hash in tx_hashes:
        try:
            tx_fee, storage_fee, combined_fee = apply_transaction(node, work_block, tx_hash)
            total_transaction_fee += int(tx_fee)
            total_storage_fee += int(storage_fee)
            total_fee += int(combined_fee)
        except Exception:
            node.logger.warning(
                "Block verify failed applying tx=%s block=%s",
                _hex(tx_hash),
                _hex(block.atom_hash),
            )
            return False

    if block.total_transaction_fee is None:
        node.logger.warning("Block verify missing total transaction fee block=%s", _hex(block.atom_hash))
        return False
    if int(block.total_transaction_fee) != int(total_transaction_fee):
        node.logger.warning(
            "Block verify total transaction fee mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            total_transaction_fee,
            block.total_transaction_fee,
        )
        return False
    if block.total_storage_fee is None:
        node.logger.warning("Block verify missing total storage fee block=%s", _hex(block.atom_hash))
        return False
    if int(block.total_storage_fee) != int(total_storage_fee):
        node.logger.warning(
            "Block verify total storage fee mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            total_storage_fee,
            block.total_storage_fee,
        )
        return False
    if int(block.total_fee) != int(total_fee):
        node.logger.warning(
            "Block verify total fee mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            total_fee,
            block.total_fee,
        )
        return False
    if block.cumulative_transaction_fee is None:
        node.logger.warning("Block verify missing cumulative transaction fee block=%s", _hex(block.atom_hash))
        return False
    expected_cumulative_transaction_fee = int(prev_block.cumulative_transaction_fee) + int(total_transaction_fee)
    if int(block.cumulative_transaction_fee) != expected_cumulative_transaction_fee:
        node.logger.warning(
            "Block verify cumulative transaction fee mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            expected_cumulative_transaction_fee,
            block.cumulative_transaction_fee,
        )
        return False
    if block.cumulative_storage_fee is None:
        node.logger.warning("Block verify missing cumulative storage fee block=%s", _hex(block.atom_hash))
        return False
    expected_cumulative_storage_fee = int(prev_block.cumulative_storage_fee) + int(total_storage_fee)
    if int(block.cumulative_storage_fee) != expected_cumulative_storage_fee:
        node.logger.warning(
            "Block verify cumulative storage fee mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            expected_cumulative_storage_fee,
            block.cumulative_storage_fee,
        )
        return False
    if block.cumulative_mint is None:
        node.logger.warning("Block verify missing cumulative mint block=%s", _hex(block.atom_hash))
        return False
    expected_cumulative_mint = prev_block.cumulative_mint + int(getattr(work_block, "total_mint", 0) or 0)
    if int(block.cumulative_mint) != expected_cumulative_mint:
        node.logger.warning(
            "Block verify cumulative mint mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            expected_cumulative_mint,
            block.cumulative_mint,
        )
        return False

    applied_transactions = list(work_block.transactions or [])
    if len(applied_transactions) != len(tx_hashes):
        node.logger.warning(
            "Block verify tx count mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            len(tx_hashes),
            len(applied_transactions),
        )
        return False

    expected_receipts: List[Receipt] = list(work_block.receipts or [])
    if len(expected_receipts) != len(applied_transactions):
        node.logger.warning(
            "Block verify receipt count mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            len(applied_transactions),
            len(expected_receipts),
        )
        return False
    expected_receipt_ids: List[bytes] = []
    for receipt in expected_receipts:
        receipt_id, _ = receipt.atomize()
        expected_receipt_ids.append(receipt_id)

    expected_receipts_head, _ = bytes_list_to_atoms(expected_receipt_ids)
    if expected_receipts_head != (block.receipts_hash or ZERO32):
        node.logger.warning(
            "Block verify receipts head mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            _hex(expected_receipts_head),
            _hex(block.receipts_hash),
        )
        return False

    stored_receipt_ids = _load_hash_list(block.receipts_hash)
    if stored_receipt_ids is None:
        node.logger.warning("Block verify failed loading receipts list block=%s", _hex(block.atom_hash))
        return False
    if stored_receipt_ids != expected_receipt_ids:
        node.logger.warning("Block verify receipts list mismatch block=%s", _hex(block.atom_hash))
        return False
    for expected, stored_id in zip(expected_receipts, stored_receipt_ids):
        try:
            stored = Receipt.from_storage(node, stored_id)
        except Exception:
            node.logger.warning(
                "Block verify failed loading receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.transaction_hash != expected.transaction_hash:
            node.logger.warning(
                "Block verify receipt tx mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.status != expected.status:
            node.logger.warning(
                "Block verify receipt status mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.transaction_fee != expected.transaction_fee:
            node.logger.warning(
                "Block verify receipt transaction fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.storage_fee != expected.storage_fee:
            node.logger.warning(
                "Block verify receipt storage fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.total_fee != expected.total_fee:
            node.logger.warning(
                "Block verify receipt total fee mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False
        if stored.logs_hash != expected.logs_hash:
            node.logger.warning(
                "Block verify receipt logs hash mismatch receipt=%s block=%s",
                _hex(stored_id),
                _hex(block.atom_hash),
            )
            return False

    try:
        accounts_snapshot.update_trie(node)
    except Exception:
        node.logger.warning("Block verify failed updating accounts trie block=%s", _hex(block.atom_hash))
        return False
    if accounts_snapshot.root_hash != block.accounts_hash:
        node.logger.warning(
            "Block verify accounts hash mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            _hex(accounts_snapshot.root_hash),
            _hex(block.accounts_hash),
        )
        return False
    treasury_account = accounts_snapshot.get_account(TREASURY_ADDRESS, node)
    if treasury_account is None:
        node.logger.warning("Block verify missing treasury account block=%s", _hex(block.atom_hash))
        return False
    treasury_balance = int(treasury_account.balance or 0)
    burn_account = accounts_snapshot.get_account(BURN_ADDRESS, node)
    if burn_account is None:
        node.logger.warning("Block verify missing burn account block=%s", _hex(block.atom_hash))
        return False
    burn_balance = int(burn_account.balance or 0)
    if block.cumulative_stake is None:
        node.logger.warning("Block verify missing cumulative stake block=%s", _hex(block.atom_hash))
        return False
    expected_cumulative_stake = prev_block.cumulative_stake + treasury_balance
    if int(block.cumulative_stake) != expected_cumulative_stake:
        node.logger.warning(
            "Block verify cumulative stake mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            expected_cumulative_stake,
            block.cumulative_stake,
        )
        return False
    if block.cumulative_burn is None:
        node.logger.warning("Block verify missing cumulative burn block=%s", _hex(block.atom_hash))
        return False
    expected_cumulative_burn = prev_block.cumulative_burn + burn_balance
    if int(block.cumulative_burn) != expected_cumulative_burn:
        node.logger.warning(
            "Block verify cumulative burn mismatch block=%s expected=%s actual=%s",
            _hex(block.atom_hash),
            expected_cumulative_burn,
            block.cumulative_burn,
        )
        return False

    node.logger.debug("Block verify success block=%s", _hex(block.atom_hash))
    return True
