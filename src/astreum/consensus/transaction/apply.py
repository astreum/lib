from __future__ import annotations

from typing import Any

from ...machine.models.expression import Expr, NIL
from ...machine.models.expression import ZERO32
from ...validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..account import create_account
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
from .storage.initial import generate_initial_storage_record, handle_storage_initial_contract
from .storage.payment import handle_storage_payment_contract
from .treasury.borrow import handle_treasury_borrow
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
    
    mandatory_storage_cost = calculate_transaction_costs(block=block, transaction=transaction)

    if sender_account.balance < tx_fee + mandatory_storage_cost:
        raise ValueError("insufficient balance for transaction fee and storage cost")
    
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
    if sender_account.balance < tx_fee + transfer_amount + mandatory_storage_cost + max_execution_fee:
        receipt_status = STATUS_FAILED
        transfer_amount = 0

    def _get_or_create_recipient_account() -> Any:
        if transaction.recipient == transaction.sender:
            return sender_account
        if transaction.recipient == BURN_ADDRESS:
            return burn_account
        account = block.accounts.get_account(address=transaction.recipient, node=node)
        if account is None:
            account = create_account()
        return account

    recipient_account = None

    match transaction.code:
        case TransactionCode.TRANSFER:
            recipient_account = _get_or_create_recipient_account()
            recipient_account.balance += transfer_amount

        case TransactionCode.CHANNEL_UPDATE:
            if transaction.recipient != transaction.sender:
                receipt_status = STATUS_FAILED
                transfer_amount = 0
            else:
                recipient_account = sender_account
                if receipt_status == STATUS_SUCCESS:
                    channel_update_success = handle_channel_update(
                        node=node,
                        block=block,
                        sender_account=sender_account,
                        payload=transaction.data,
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
                channel_close_success = handle_channel_close(
                    node=node,
                    block=block,
                    sender_account=sender_account,
                    payload=transaction.data,
                )
                if not channel_close_success:
                    receipt_status = STATUS_FAILED

        case TransactionCode.TREASURY_DEPOSIT:
            recipient_account = _get_or_create_recipient_account()
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
            transfer_amount = 0
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
            recipient_account = _get_or_create_recipient_account()
            if transaction.recipient != BURN_ADDRESS:
                transfer_amount = 0
                pass
            else:
                if transfer_amount > 0:
                    receipt_status = STATUS_FAILED
                    transfer_amount = 0
                if receipt_status == STATUS_SUCCESS:
                    initial_contract_storage_fee = handle_storage_initial_contract(
                        node=node,
                        block=block,
                        transaction=transaction,
                        sender_account=sender_account,
                        burn_account=burn_account,
                        expr_list_id=transaction.data,
                        current_fees=tx_fee + transfer_amount + mandatory_storage_cost,
                    )
                    if initial_contract_storage_fee is None:
                        receipt_status = STATUS_FAILED
                if transfer_amount > 0:
                    recipient_account.balance += transfer_amount

        case TransactionCode.STORAGE_PAYMENT:
            recipient_account = _get_or_create_recipient_account()
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
            recipient_account = _get_or_create_recipient_account()
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
                receipt_status, execution_fee = handle_expression_account_call(
                    node=node,
                    block=block,
                    transaction=transaction,
                )
                tx_fee += int(execution_fee)
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
            else:
                transfer_amount = 0

        case _:
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

    sender_account.balance -= tx_fee + transfer_amount + mandatory_storage_cost
    burn_account.balance += mandatory_storage_cost

    block.accounts.set_account(transaction.sender, sender_account)
    if recipient_account is not None:
        block.accounts.set_account(transaction.recipient, recipient_account)
    block.accounts.set_account(BURN_ADDRESS, burn_account)

    # Bloom Filter
    # Create standard bloom filter keys
    bloom_inserts: list[bytes] = make_search_variants(
        tx_hash=transaction_hash,
        sender=transaction.sender,
        receiver=transaction.recipient,
    )

    # STORAGE
    # calculate bloom fee = block storage fee * (2 * num_of_inserts)
    bloom_fee = calculate_storage_fee(block, 2 * len(bloom_inserts))

    # Store Transaction
    # calculate storage fee
    tx_result = generate_initial_storage_record(node, block, transaction.expr())
    if tx_result is None:
        receipt_status = STATUS_FAILED
        tx_storage_fee = 0
    else:
        tx_record, tx_slot_map, _tx_found, tx_storage_fee = tx_result
    # check user has enough balance
    current_cumulative_storage_fee = tx_storage_fee + bloom_fee
    if sender_account.balance < current_cumulative_storage_fee:
        receipt_status = STATUS_FAILED

    logs_expr = NIL
    # Store Receipt

    # Calculate receipt content bytes:
    # storage_fee cumulative (in receipt) + tx_fee bytes + logs size + symbol size + link fee + status
    receipt_bytes = (
        ((current_cumulative_storage_fee).bit_length() + 7) // 8  # storage_fee int byte width
        + ((tx_fee).bit_length() + 7) // 8        # tx_fee int byte width
        + logs_expr.size()                         # logs content
        + 7                                        # Symbol("receipt")
        + 10 * 32                                  # link overhead (10 Links × 32)
        + 1                                        # status byte
    )
    receipt_fee = calculate_storage_fee(block, receipt_bytes)

    current_cumulative_storage_fee += receipt_fee

    # create receipt with the correct total from the start
    receipt = Receipt(
        transaction_hash=transaction_hash,
        transaction_fee=tx_fee,
        storage_fee=current_cumulative_storage_fee,
        status=receipt_status,
        logs_hash=ZERO32,
    )
    # calculate storage fee for receipt
    receipt_result = generate_initial_storage_record(node, block, receipt.expr())
    if receipt_result is None:
        receipt_status = STATUS_FAILED
    else:
        receipt_record, receipt_slot_map, _, _ = receipt_result
    # check user has enough balance
    if sender_account.balance < current_cumulative_storage_fee:
        receipt_status = STATUS_FAILED

    # Append to block
    if block.transactions is None:
        block.transactions = []
    block.transactions.append(transaction)

    if block.receipts is None:
        block.receipts = []
    block.receipts.append(receipt)

    # Insert storage contracts into burn data
    if tx_result is not None:
        burn_account.data.put(node, transaction_hash, tx_record.expr())
        burn_account.data_hash = burn_account.data.root_hash
        block.pending_exprs.append(tx_record.expr())
        for h, slot in tx_slot_map.items():
            burn_account.data.put(node, h, slot.expr())
            block.pending_exprs.append(slot.expr())
        # Fetch actual data exprs by hash (tx root + new sub-exprs)
        tx_expr = node.get_expr(transaction_hash)
        if tx_expr is not None:
            block.pending_exprs.append(tx_expr)
        for h in tx_slot_map:
            sub_expr = node.get_expr(h)
            if sub_expr is not None:
                block.pending_exprs.append(sub_expr)

    if receipt_result is not None:
        burn_account.data.put(node, receipt.expr().hash(), receipt_record.expr())
        burn_account.data_hash = burn_account.data.root_hash
        block.pending_exprs.append(receipt_record.expr())
        for h, slot in receipt_slot_map.items():
            burn_account.data.put(node, h, slot.expr())
            block.pending_exprs.append(slot.expr())
        # Fetch actual data exprs by hash (receipt root + new sub-exprs)
        receipt_hash = receipt.expr().hash()
        rcpt_expr = node.get_expr(receipt_hash)
        if rcpt_expr is not None:
            block.pending_exprs.append(rcpt_expr)
        for h in receipt_slot_map:
            sub_expr = node.get_expr(h)
            if sub_expr is not None:
                block.pending_exprs.append(sub_expr)

    # Bloom filter
    # Insert search keys into block bloom filter
    block_offset = block.height % 1024
    block.bloom_tree.insert(block_offset, bloom_inserts)
