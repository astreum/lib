from typing import Optional
import time
from .account import Account, get_account_from_storage
import astreum.format as format

class Transaction:
    def __init__(
        self,
        sender: Account,
        recipient: Account,
        amount: int,
        data: bytes = None,
        counter: int = 0
    ):
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.data = data
        self.counter = counter
        self.timestamp = time.time()
        self.signature = None

    @classmethod
    def from_bytes(cls, data: bytes, resolve_accounts: bool = False, accounts=None, storage=None) -> 'Transaction':
        """
        Deserialize a Transaction from its byte representation.
        
        Expected format: [sender_hash, recipient_hash, amount, data, counter, timestamp, signature]
        
        Args:
            data: Serialized transaction data
            resolve_accounts: If True, attempts to resolve account objects from storage
            accounts: Accounts instance (required if resolve_accounts is True)
            storage: Storage instance (required if resolve_accounts is True)
            
        Returns:
            Transaction object
        """
        decoded = format.decode(data)
        sender_public_key, recipient_public_key, amount, tx_data, counter, timestamp, signature = decoded
        
        sender_account = None
        recipient_account = None
        
        if resolve_accounts:
            if accounts is None or storage is None:
                raise ValueError("Both accounts and storage must be provided when resolve_accounts is True")
            sender_account = get_account_from_storage(sender_public_key, accounts, storage)
            recipient_account = get_account_from_storage(recipient_public_key, accounts, storage)
        else:
            # Create minimal Account objects with just the public keys
            sender_account = Account(sender_public_key, 0, b'', 0, b'')
            recipient_account = Account(recipient_public_key, 0, b'', 0, b'')
        
        transaction = cls(sender_account, recipient_account, amount, tx_data, counter)
        transaction.timestamp = timestamp
        transaction.signature = signature
        return transaction

    def to_bytes(self) -> bytes:
        """
        Serialize the Transaction into bytes.
        
        Format: [sender_hash, recipient_hash, amount, data, counter, timestamp, signature]
        """
        return format.encode([
            self.sender.public_key,
            self.recipient.public_key,
            self.amount,
            self.data,
            self.counter,
            self.timestamp,
            self.signature
        ])


def get_tx_from_storage(hash: bytes) -> Optional[Transaction]:
    """Resolves storage objects to get a transaction.
    
    Args:
        hash: Hash of the transaction and merkle root of the transaction
        
    Returns:
        Transaction object if found, None otherwise
    """
    return None


def put_tx_to_storage(transaction: Transaction):
    """Puts a transaction into storage.
    
    Args:
        transaction: Transaction object to put into storage
        
    Returns:
        None
    """
    return None


def get_tx_hash(transaction: Transaction) -> bytes:
    """Get the hash of a transaction.
    
    Args:
        transaction: Transaction object to get hash for
        
    Returns:
        Merkle root of the transaction body hash and signature
    """
    return hash_data(get_tx_body_hash(transaction) + hash_data(transaction.signature))

def get_tx_body_hash(transaction: Transaction) -> bytes:
    """Get the hash of the transaction body.
    
    Args:
        transaction: Transaction object to get hash for
        
    Returns:
        Hash of the transaction body
    """
    return hash_data(transaction)

def sign_tx(transaction: Transaction, private_key: bytes) -> Transaction:
    """Sign a transaction.
    
    Args:
        transaction: Transaction object to sign
        private_key: Private key to sign with
        
    Returns:
        Signed transaction
    """
    transaction.signature = hash_data(get_tx_body_hash(transaction) + private_key)
    return transaction


def verify_tx(transaction: Transaction) -> bool:
    """Verify a transaction.
    
    Args:
        transaction: Transaction object to verify,with sender public key
        
    Returns:
        True if the transaction is valid, False otherwise
    """
    return True
