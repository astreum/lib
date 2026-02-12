from __future__ import annotations

from typing import Any

from ...storage.models.atom import ZERO32
from ...utils.integer import bytes_to_int, int_to_bytes
from ...validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ...validation.models.account import Account
from ...validation.models.receipt import STATUS_FAILED, Receipt, STATUS_SUCCESS
from .model import Transaction
from .storage_initial import handle_storage_initial_contract
from .storage_payment import handle_storage_payment_contract


def _append_failure_receipt(block: object, transaction_hash: bytes, transaction: Transaction) -> None:
    failure_receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        cost=0,
        status=STATUS_FAILED,
    )
    failure_receipt.atomize()
    if block.receipts is None:
        block.receipts = []
    block.receipts.append(failure_receipt)
    if block.transactions is None:
        block.transactions = []
    block.transactions.append(transaction)


def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> int:
    """Apply transaction to the candidate block and return the collected fee."""
    transaction = Transaction.from_storage(node, transaction_hash)

    block_chain = getattr(block, "chain_id", None)
    if block_chain is not None and transaction.chain_id != block_chain:
        return 0

    accounts = getattr(block, "accounts", None)
    if accounts is None:
        raise ValueError("block missing accounts snapshot for transaction application")

    sender_account = accounts.get_account(address=transaction.sender, node=node)
    if sender_account is None:
        return 0

    tx_fee = 1
    if sender_account.balance < tx_fee:
        _append_failure_receipt(block, transaction_hash, transaction)
        return 0

    transfer_amount = transaction.amount

    recipient_account = accounts.get_account(address=transaction.recipient, node=node)
    if recipient_account is None:
        recipient_account = Account.create()

    if transaction.recipient == BURN_ADDRESS and transaction.data:
        contract_flag = transaction.data[0]
        payload = transaction.data[1:]
        if contract_flag == 0:
            contract_atoms = handle_storage_initial_contract(
                node=node,
                block=block,
                transaction=transaction,
                sender_account=sender_account,
                burn_account=recipient_account,
                payload=payload,
                tx_fee=tx_fee,
            )
            if not contract_atoms:
                _append_failure_receipt(block, transaction_hash, transaction)
                return 0
            if not hasattr(block, "contract_atoms") or block.contract_atoms is None:
                block.contract_atoms = []
            block.contract_atoms.extend(contract_atoms)
            transfer_amount = 0
        elif contract_flag == 1:
            handle_storage_payment_contract(
                node=node,
                block=block,
                transaction=transaction,
                sender_account=sender_account,
                burn_account=recipient_account,
                payload=payload,
            )

    if sender_account.balance < tx_fee + transfer_amount:
        _append_failure_receipt(block, transaction_hash, transaction)
        return 0

    if transaction.recipient == TREASURY_ADDRESS:
        stake_trie = recipient_account.data
        existing_stake = stake_trie.get(node, transaction.sender)
        current_stake = bytes_to_int(existing_stake)
        new_stake = current_stake + transfer_amount
        stake_trie.put(node, transaction.sender, int_to_bytes(new_stake))
        recipient_account.data_hash = stake_trie.root_hash or ZERO32
        recipient_account.balance += transfer_amount
    else:
        recipient_account.balance += transfer_amount

    sender_account.balance -= tx_fee + transfer_amount
    accounts.set_account(transaction.sender, sender_account)
    accounts.set_account(transaction.recipient, recipient_account)

    if block.transactions is None:
        block.transactions = []
    block.transactions.append(transaction)

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        cost=tx_fee,
        status=STATUS_SUCCESS,
    )
    receipt.atomize()
    if block.receipts is None:
        block.receipts = []
    block.receipts.append(receipt)
    return tx_fee
