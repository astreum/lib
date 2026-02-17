from __future__ import annotations

from typing import Any

from ...storage.models.atom import ZERO32
from ...utils.integer import bytes_to_int, int_to_bytes
from ...validation.constants import BURN_ADDRESS, TREASURY_ADDRESS
from ..account import create_account
from ...validation.models.receipt import Receipt, STATUS_FAILED, STATUS_SUCCESS
from .from_storage import get_transaction_from_storage
from .channel.close import OP_CLOSE, handle_channel_close
from .channel.update import OP_UPDATE, handle_channel_update
from .channel.withdraw import OP_WITHDRAW, handle_channel_withdraw
from .storage_contract import (
    calculate_transaction_costs,
    generate_receipt_storage_contract,
    generate_transaction_storage_contract,
)
from .storage_initial import handle_storage_initial_contract
from .storage_payment import handle_storage_payment_contract

def apply_transaction(node: Any, block: object, transaction_hash: bytes) -> int:
    """Apply transaction to the candidate block and return the collected fee."""
    transaction = get_transaction_from_storage(node, transaction_hash)

    if transaction.chain_id != block.chain_id:
        raise ValueError("transaction chain_id does not match block chain_id")

    sender_account = block.accounts.get_account(address=transaction.sender, node=node)
    if sender_account is None:
        raise ValueError("sender account not found")
    burn_account = block.accounts.get_account(address=BURN_ADDRESS, node=node)

    receipt_status = STATUS_SUCCESS
    collected_fee = 0
    tx_fee = 1
    if sender_account.balance < tx_fee:
        raise ValueError("insufficient balance for transaction fee")
    
    mandatory_storage_cost = calculate_transaction_costs(block=block, transaction=transaction)

    if sender_account.balance < tx_fee + mandatory_storage_cost:
        raise ValueError("insufficient balance for transaction fee and storage cost")
    
    transfer_amount = transaction.amount
    if (
        transaction.recipient == transaction.sender
        and transaction.data
        and transaction.data[0] == OP_WITHDRAW
    ):
        transfer_amount = 0

    if transaction.recipient == BURN_ADDRESS and transaction.data and transaction.data[0] == 0 and transfer_amount > 0:
        receipt_status = STATUS_FAILED
        transfer_amount = 0
    if sender_account.balance < tx_fee + transfer_amount + mandatory_storage_cost:
        receipt_status = STATUS_FAILED
        transfer_amount = 0

    if transaction.recipient == transaction.sender:
        recipient_account = sender_account

        if transaction.data and transaction.data[0] == OP_UPDATE and receipt_status == STATUS_SUCCESS:
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
        elif transaction.data and transaction.data[0] == OP_CLOSE and receipt_status == STATUS_SUCCESS:
            transfer_amount = 0
            channel_close_success = handle_channel_close(
                node=node,
                block=block,
                sender_account=sender_account,
                payload=transaction.data,
            )
            if not channel_close_success:
                receipt_status = STATUS_FAILED
        elif transaction.data and transaction.data[0] == OP_WITHDRAW and receipt_status == STATUS_SUCCESS:
            transfer_amount = 0
            channel_withdraw_success = handle_channel_withdraw(
                node=node,
                block=block,
                sender_account=sender_account,
                payload=transaction.data,
                chain_id=transaction.chain_id,
                recipient=transaction.sender,
            )
            if not channel_withdraw_success:
                receipt_status = STATUS_FAILED
        else:
            # Non-channel self-transfers are fee-only.
            transfer_amount = 0

    elif transaction.recipient == TREASURY_ADDRESS:
        recipient_account = block.accounts.get_account(address=transaction.recipient, node=node)
        stake_trie = recipient_account.data
        existing_stake = stake_trie.get(node, transaction.sender)
        current_stake = bytes_to_int(existing_stake)
        new_stake = current_stake + transfer_amount
        stake_trie.put(node, transaction.sender, int_to_bytes(new_stake))
        recipient_account.data_hash = stake_trie.root_hash or ZERO32
        recipient_account.balance += transfer_amount
    
    elif transaction.recipient == BURN_ADDRESS:
        recipient_account = burn_account
        if transaction.data:
            contract_flag = transaction.data[0]
            payload = transaction.data[1:]
            if contract_flag == 0:
                initial_contract_success = handle_storage_initial_contract(
                    node=node,
                    block=block,
                    transaction=transaction,
                    sender_account=sender_account,
                    burn_account=burn_account,
                    atom_list_id=payload,
                    current_fees=tx_fee + transfer_amount + mandatory_storage_cost,
                )
                if not initial_contract_success:
                    receipt_status = STATUS_FAILED
            elif contract_flag == 1:
                payment_contract_success = handle_storage_payment_contract(
                    node=node,
                    block=block,
                    transaction=transaction,
                    sender_account=sender_account,
                    burn_account=burn_account,
                    payload=payload,
                )
                if not payment_contract_success:
                    receipt_status = STATUS_FAILED
        if transfer_amount > 0:
            recipient_account.balance += transfer_amount
    
    else:
        recipient_account = block.accounts.get_account(address=transaction.recipient, node=node)
        if recipient_account is None:
            recipient_account = create_account()

        recipient_account.balance += transfer_amount

    # mandatory storage contracts 
    generate_transaction_storage_contract(
        node=node,
        block=block,
        transaction_hash=transaction_hash,
        transaction=transaction,
        sender_account=sender_account,
        burn_account=burn_account,
    )

    receipt = Receipt(
        transaction_hash=bytes(transaction_hash),
        status=receipt_status,
        cost=tx_fee,
    )
    generate_receipt_storage_contract(
        node=node,
        block=block,
        sender_account=sender_account,
        burn_account=burn_account,
        receipt=receipt,
        sender_public_key=transaction.sender,
    )

    sender_account.balance -= tx_fee + transfer_amount
    
    block.accounts.set_account(transaction.sender, sender_account)
    block.accounts.set_account(transaction.recipient, recipient_account)
    
    block.transactions.append(transaction)
    block.receipts.append(receipt)
    block.accounts.set_account(BURN_ADDRESS, burn_account)
    return collected_fee
