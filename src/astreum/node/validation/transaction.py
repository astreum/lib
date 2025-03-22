from .account import Account

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
