from __future__ import annotations

from typing import Any

from ...machine.models.expression import Expr, NIL
from ...machine.models.expression import ZERO32
from ...machine.models.expression.helpers import exprs_to_linked_expr
from ...storage.models.trie import Trie
from ...validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..account import create_account
from ..account.model import generate_new_account_storage_contracts
from ...validation.models.receipt import STATUS_FAILED, STATUS_SUCCESS, Receipt
from ..block.rate import calculate_storage_fee
from ...crypto.bloom_search import make_search_variants
from .code import TransactionCode
from .from_storage import get_transaction_from_storage
from .accounts.create import handle_expression_account_create
from .accounts.expression import handle_expression_account_call
from .channel.close import handle_channel_close
from .channel.update import handle_channel_update
from .channel.withdraw import handle_channel_withdraw
from .storage.contract import (
    calculate_transaction_costs,
)
from .storage.initial import handle_storage_initial_contract
from .storage.pending import add_pending_storage_contract
from .storage.payment import handle_storage_payment_contract
from .treasury.borrow import handle_treasury_borrow
from .bloom.pending import finalize_pending_bloom_inserts
from .treasury.record import (
    TreasuryUserRecord,
)
from .treasury.close import handle_treasury_close
from .treasury.repay import handle_treasury_repay


def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> None:
    """Apply a transaction, collecting results on *block*."""
    transaction = get_transaction_from_storage(node, transaction_hash)

    if transaction.chain_id != block.chain_id:
        raise ValueError("transaction chain_id does not match block chain_id")

    sender_account = block.accounts.get_account(address=transaction.sender, node=node)
    if sender_account is None:
        raise ValueError("sender account not found")
    burn_account = block.accounts.get_account(address=BURN_ADDRESS, node=node)

    receipt_status = STATUS_SUCCESS
    tx_fee = 1
    if sender_account.balance < tx_fee:
        raise ValueError("insufficient balance for transaction fee")
    
    transfer_amount = transaction.amount
    if transaction.code in (TransactionCode.CHANNEL_WITHDRAW, TransactionCode.TREASURY_BORROW):
        transfer_amount = 0

    if (
        transaction.recipient == BURN_ADDRESS
        and transaction.code == TransactionCode.STORAGE_CREATE
        and transfer_amount > 0
    ):
        receipt_status = STATUS_FAILED
        transfer_amount = 0
    max_execution_fee = (
        max(0, int(transaction.cost_limit))
        if transaction.code == TransactionCode.CODE_ACCOUNT_CALL
        else 0
    )
    if sender_account.balance < tx_fee + transfer_amount + max_execution_fee:
        receipt_status = STATUS_FAILED
        transfer_amount = 0

    def _get_or_create_recipient_account() -> tuple["Account", bool]:
        if transaction.recipient == transaction.sender:
            return sender_account, False
        if transaction.recipient == BURN_ADDRESS:
            return burn_account, False
        account = block.accounts.get_account(address=transaction.recipient, node=node)
        if account is None:
            return (create_account(),True)
            
        return (account, False)

    recipient_account = None
    is_recipient_new = False

    # data fee is sender + receiptient sizes
    current_data_fee = 0
    current_evaluation_fee = 0
    current_storage_fee = 0
    collected_logs: list[Expr] = []

    match transaction.code:
        case TransactionCode.TRANSFER:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            recipient_account.balance += transfer_amount

        case TransactionCode.CHANNEL_UPDATE:
            if transaction.recipient != transaction.sender:
                receipt_status = STATUS_FAILED
                transfer_amount = 0
            else:
                recipient_account = sender_account
                if receipt_status == STATUS_SUCCESS:
                    tx_data_bytes = transaction.data.value if transaction.data._tag == "bytes" else b""
                    channel_update_success = handle_channel_update(
                        node=node,
                        block=block,
                        sender_account=sender_account,
                        payload=tx_data_bytes,
                        tx_amount=transaction.amount,
                    )
                    if not channel_update_success:
                        receipt_status = STATUS_FAILED
                        transfer_amount = 0

        case TransactionCode.CHANNEL_WITHDRAW:
            transfer_amount = 0
            recipient_account = block.accounts.get_account(address=transaction.recipient, node=node)
            if receipt_status == STATUS_SUCCESS:
                if recipient_account is None:
                    receipt_status = STATUS_FAILED
                else:
                    channel_withdraw_success = handle_channel_withdraw(
                        node=node,
                        block=block,
                        sender_account=sender_account,
                        transaction=transaction,
                    )
                    if not channel_withdraw_success:
                        receipt_status = STATUS_FAILED

        case TransactionCode.CHANNEL_CLOSE:
            transfer_amount = 0
            if transaction.recipient != transaction.sender:
                receipt_status = STATUS_FAILED
            elif receipt_status == STATUS_SUCCESS:
                tx_data_bytes = transaction.data.value if transaction.data._tag == "bytes" else b""
                channel_close_success = handle_channel_close(
                    node=node,
                    block=block,
                    sender_account=sender_account,
                    payload=tx_data_bytes,
                )
                if not channel_close_success:
                    receipt_status = STATUS_FAILED

        case TransactionCode.TREASURY_DEPOSIT:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            if transaction.recipient != TREASURY_ADDRESS:
                transfer_amount = 0
                pass
            elif receipt_status == STATUS_SUCCESS:
                stake_trie = recipient_account.data
                existing_record_head = stake_trie.get(node, transaction.sender)
                if not existing_record_head or existing_record_head == ZERO32:
                    receipt_status = STATUS_FAILED
                    transfer_amount = 0
                else:
                    treasury_user_record = TreasuryUserRecord.from_storage(
                        node,
                        existing_record_head,
                    )
                    if treasury_user_record is None:
                        receipt_status = STATUS_FAILED
                        transfer_amount = 0
                    else:
                        updated_stake_record = TreasuryUserRecord(
                            balance=(
                                treasury_user_record.balance + transfer_amount
                            ),
                            loans_root_hash=treasury_user_record.loans_root_hash,
                            total_interest_paid=treasury_user_record.total_interest_paid,
                        )
                        updated_record_head = updated_stake_record.expr().hash()
                        stake_trie.put(node, transaction.sender, updated_record_head)
                recipient_account.data_hash = stake_trie.root_hash or ZERO32
                recipient_account.balance += transfer_amount

        case TransactionCode.TREASURY_BORROW:
            transfer_amount = 0
            treasury_account = block.accounts.get_account(address=TREASURY_ADDRESS, node=node)
            recipient_account = treasury_account
            if receipt_status == STATUS_SUCCESS:
                receipt_status = handle_treasury_borrow(
                    node=node,
                    block=block,
                    transaction=transaction,
                    transaction_hash=transaction_hash,
                    sender_account=sender_account,
                    treasury_account=treasury_account,
                )

        case TransactionCode.TREASURY_CLOSE:
            treasury_account = block.accounts.get_account(address=TREASURY_ADDRESS, node=node)
            if treasury_account is not None:
                recipient_account = treasury_account
            if receipt_status == STATUS_SUCCESS:
                receipt_status = handle_treasury_close(
                    node=node,
                    block=block,
                    transaction=transaction,
                )
                if receipt_status != STATUS_SUCCESS:
                    transfer_amount = 0
            else:
                transfer_amount = 0

        case TransactionCode.TREASURY_REPAY:
            treasury_account = block.accounts.get_account(address=TREASURY_ADDRESS, node=node)
            if transaction.recipient == TREASURY_ADDRESS:
                recipient_account = treasury_account
            if receipt_status == STATUS_SUCCESS:
                receipt_status = handle_treasury_repay(
                    node=node,
                    block=block,
                    transaction=transaction,
                )
                if receipt_status != STATUS_SUCCESS:
                    transfer_amount = 0
            else:
                transfer_amount = 0

        case TransactionCode.STORAGE_CREATE:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            if transaction.recipient != BURN_ADDRESS:
                transfer_amount = 0
                pass
            else:
                if transfer_amount > 0:
                    receipt_status = STATUS_FAILED
                    transfer_amount = 0
                if receipt_status == STATUS_SUCCESS:
                    expr_list_id = transaction.data.value if transaction.data._tag == "bytes" else b""
                    initial_contract_storage_fee = handle_storage_initial_contract(
                        node=node,
                        block=block,
                        transaction=transaction,
                        sender_account=sender_account,
                        burn_account=burn_account,
                        expr_list_id=expr_list_id,
                        current_fees=tx_fee + transfer_amount,
                    )
                    if initial_contract_storage_fee is None:
                        receipt_status = STATUS_FAILED
                if transfer_amount > 0:
                    recipient_account.balance += transfer_amount

        case TransactionCode.STORAGE_PAYMENT:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            if transaction.recipient != BURN_ADDRESS:
                transfer_amount = 0
                pass
            else:
                if receipt_status == STATUS_SUCCESS:
                    payment_contract_success = handle_storage_payment_contract(
                        node=node,
                        block=block,
                        transaction=transaction,
                        sender_account=sender_account,
                        burn_account=burn_account,
                        payload=transaction.data,
                    )
                    if not payment_contract_success:
                        receipt_status = STATUS_FAILED
                if transfer_amount > 0:
                    recipient_account.balance += transfer_amount

        case TransactionCode.STORAGE_REMOVE:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

        case TransactionCode.CODE_ACCOUNT_CREATE:
            if receipt_status == STATUS_SUCCESS:
                expression_create_success = handle_expression_account_create(
                    node=node,
                    block=block,
                    transaction=transaction,
                    transaction_hash=transaction_hash,
                )
                if not expression_create_success:
                    receipt_status = STATUS_FAILED
                    transfer_amount = 0
            else:
                transfer_amount = 0

        case TransactionCode.CODE_ACCOUNT_CALL:
            if receipt_status == STATUS_SUCCESS:
                receipt_status, used_eval, collected_logs = handle_expression_account_call(
                    node=node,
                    block=block,
                    transaction=transaction,
                )
                current_evaluation_fee = int(used_eval)
                tx_fee += current_evaluation_fee
                if receipt_status != STATUS_SUCCESS:
                    transfer_amount = 0
                else:
                    sender_account = block.accounts.get_account(
                        address=transaction.sender,
                        node=node,
                    )
                    burn_account = block.accounts.get_account(
                        address=BURN_ADDRESS,
                        node=node,
                    )
                    recipient_account = block.accounts.get_account(
                        address=transaction.recipient,
                        node=node,
                    )
            else:
                transfer_amount = 0

        case _:
            (recipient_account, is_recipient_new) = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

    # Bloom Filter
    bloom_inserts: list[bytes] = make_search_variants(
        tx_hash=transaction_hash,
        sender=transaction.sender,
        receiver=transaction.recipient,
    )

    block_offset = block.height % 1024
    block.bloom_tree.insert(block_offset, bloom_inserts)

    bloom_storage_fee = calculate_storage_fee(block, 2 * len(bloom_inserts))
    current_storage_fee += bloom_storage_fee
    if sender_account.balance < tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee:
        receipt_status = STATUS_FAILED

    operator_bloom_fee = finalize_pending_bloom_inserts(node, block, transaction, receipt_status)
    current_storage_fee += operator_bloom_fee
    if sender_account.balance < tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee:
        receipt_status = STATUS_FAILED


    # Transaction
    transaction_storage_fee = add_pending_storage_contract(node, block, None, None, transaction.expr())
    if transaction_storage_fee is None:
        receipt_status = STATUS_FAILED
    else:
        current_storage_fee += transaction_storage_fee
        if sender_account.balance < tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee:
            receipt_status = STATUS_FAILED
    
    # Logs
    logs_expr = NIL
    if collected_logs:
        logs_expr = exprs_to_linked_expr(collected_logs)
        logs_storage_fee = add_pending_storage_contract(node, block, None, None, logs_expr)
        if logs_storage_fee is None:
            receipt_status = STATUS_FAILED
        else:
            current_storage_fee += logs_storage_fee
            if sender_account.balance < tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee:
                receipt_status = STATUS_FAILED

    receipt = Receipt(
        transaction_hash=transaction_hash,
        transaction_fee=tx_fee,
        storage_fee=current_storage_fee,
        data_fee=current_data_fee,
        execution_fee=current_evaluation_fee,
        status=receipt_status,
        logs_hash=logs_expr.hash(),
    )

    receipt_storage_fee = add_pending_storage_contract(node, block, None, None, receipt.expr())
    if receipt_storage_fee is None:
        receipt_status = STATUS_FAILED


    # Accounts
    sender_account.balance -= tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee
    burn_account.balance += current_storage_fee

    if is_recipient_new:
        new_account_storage_fee = calculate_storage_fee(block, recipient_account.expr().size())
        current_storage_fee += new_account_storage_fee
        if sender_account.balance < tx_fee + transfer_amount + current_data_fee + current_evaluation_fee + current_storage_fee:
            receipt_status = STATUS_FAILED

        generate_new_account_storage_contracts(node, block, burn_account, recipient_account.expr())

    if recipient_account is not None:
        block.accounts.set_account(transaction.recipient, recipient_account)
    block.accounts.set_account(transaction.sender, sender_account)
    block.accounts.set_account(BURN_ADDRESS, burn_account)

    # Append to block
    if block.transactions is None:
        block.transactions = []
    block.transactions.append(transaction)

    if block.receipts_trie is None:
        block.receipts_trie = Trie()
    block.receipts_trie.put(node, transaction_hash, receipt.expr())

    if block.receipts is None:
        block.receipts = []
    block.receipts.append(receipt)
