from __future__ import annotations

from typing import Any, Tuple

from ...storage.models.atom import Atom, AtomKind, ZERO32
from ...utils.integer import bytes_to_int, int_to_bytes
from ...validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..account import create_account
from ...validation.models.receipt import Receipt, STATUS_FAILED, STATUS_SUCCESS
from .code import TransactionCode
from .from_storage import get_transaction_from_storage
from .channel.close import handle_channel_close
from .channel.update import handle_channel_update
from .channel.withdraw import handle_channel_withdraw
from .storage_contract import (
    calculate_transaction_costs,
    generate_receipt_storage_contract,
    generate_transaction_storage_contract,
)
from .storage_initial import handle_storage_initial_contract
from .storage_payment import handle_storage_payment_contract

def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> Tuple[int, int, int]:
    """Apply a transaction and return (transaction_fee, storage_fee, total_fee)."""
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
    additional_storage_fee = 0

    if sender_account.balance < tx_fee + mandatory_storage_cost:
        raise ValueError("insufficient balance for transaction fee and storage cost")
    
    transfer_amount = transaction.amount
    if transaction.code == TransactionCode.CHANNEL_WITHDRAW:
        transfer_amount = 0

    if (
        transaction.recipient == BURN_ADDRESS
        and transaction.code == TransactionCode.STORAGE_CREATE
        and transfer_amount > 0
    ):
        receipt_status = STATUS_FAILED
        transfer_amount = 0
    if sender_account.balance < tx_fee + transfer_amount + mandatory_storage_cost:
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
                    stake_atom = node.get_atom(existing_record_head)
                    if stake_atom is None or stake_atom.kind is not AtomKind.BYTES:
                        receipt_status = STATUS_FAILED
                        transfer_amount = 0
                    else:
                        updated_stake_atom = Atom(
                            data=int_to_bytes(bytes_to_int(stake_atom.data) + transfer_amount),
                            next_id=stake_atom.next_id,
                            kind=AtomKind.BYTES,
                        )
                        stake_trie.put(node, transaction.sender, updated_stake_atom.object_id())
                        if updated_stake_atom.object_id() != existing_record_head:
                            block.accounts.pending_atoms.append(updated_stake_atom)
                recipient_account.data_hash = stake_trie.root_hash or ZERO32
                recipient_account.balance += transfer_amount

        case TransactionCode.TREASURY_BORROW:
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

        case TransactionCode.TREASURY_REPAY:
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

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
                        atom_list_id=transaction.data,
                        current_fees=tx_fee + transfer_amount + mandatory_storage_cost,
                    )
                    if initial_contract_storage_fee is None:
                        receipt_status = STATUS_FAILED
                    else:
                        additional_storage_fee += int(initial_contract_storage_fee)
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
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

        case TransactionCode.CODE_ACCOUNT_CALL:
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

        case _:
            recipient_account = _get_or_create_recipient_account()
            transfer_amount = 0
            pass

    # mandatory storage contracts 
    generate_transaction_storage_contract(
        node=node,
        block=block,
        transaction_hash=transaction_hash,
        transaction=transaction,
        burn_account=burn_account,
    )

    storage_fee = mandatory_storage_cost + additional_storage_fee

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        transaction_fee=tx_fee,
        storage_fee=storage_fee,
        status=receipt_status,
    )
    generate_receipt_storage_contract(
        node=node,
        block=block,
        burn_account=burn_account,
        receipt=receipt,
        sender_public_key=transaction.sender,
    )

    sender_account.balance -= tx_fee + transfer_amount + mandatory_storage_cost
    burn_account.balance += mandatory_storage_cost
    
    block.accounts.set_account(transaction.sender, sender_account)
    if recipient_account is not None:
        block.accounts.set_account(transaction.recipient, recipient_account)
    
    block.transactions.append(transaction)
    block.receipts.append(receipt)
    block.accounts.set_account(BURN_ADDRESS, burn_account)
    return tx_fee, storage_fee, tx_fee + storage_fee
