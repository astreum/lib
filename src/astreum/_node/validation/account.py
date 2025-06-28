from typing import Optional
from ..storage.patricia import PatriciaTrie

import astreum.format as format
class Account:
    def __init__(self, public_key: bytes, balance: int, code: bytes, counter: int, data: bytes, secret_key: Optional[bytes] = None):
        """
        Initialize an Account.

        :param public_key: The public key used as the account identifier (used as trie key).
        :param balance: The account balance.
        :param code: The associated code (for example, smart contract code).
        :param counter: A transaction counter (nonce).
        :param data: Additional account data.
        :param secret_key: (Optional) The account’s secret key.
        """
        self.public_key = public_key
        self.secret_key = secret_key  # Optional private key.
        self.balance = balance
        self.code = code
        self.counter = counter
        self.data = data

    @classmethod
    def from_bytes(cls, public_key: bytes, data: bytes, secret_key: Optional[bytes] = None) -> 'Account':
        """
        Deserialize an Account from its byte representation.
        
        Expected format: [balance, code, counter, data]
        
        The public_key (and optional secret_key) must be provided separately.
    """
        decoded = format.decode(data)
        balance, code, counter, account_data = decoded
        return cls(public_key, balance, code, counter, account_data, secret_key=secret_key)
    
    def to_bytes(self) -> bytes:
        """
        Serialize the Account into bytes.
        
        Format: [balance, code, counter, data]
        """
        return format.encode([
            self.balance,
            self.code,
            self.counter,
            self.data
        ])


class Accounts(PatriciaTrie):
    """
    Accounts is a PatriciaTrie storing Account objects.
    
    The trie key is the account’s public key (bytes), while the value is the account data
    (serialized with balance, code, counter, and data only).
    
    You can instantiate Accounts with a storage instance and, if available, a root hash
    representing an existing trie.
    """
    def get_account(self, public_key: bytes) -> Optional[Account]:
        """
        Retrieve an account using its public key.

        :param public_key: The public key (bytes) of the account.
        :return: The Account instance if found, else None.
        """
        raw = self.get(public_key)
        if raw is None:
            return None
        return Account.from_bytes(public_key, raw)

    def put_account(self, account: Account) -> None:
        """
        Insert or update an account in the trie.

        :param account: The Account instance to store.
        """
        self.put(account.public_key, account.to_bytes())

def get_account_from_storage(public_key: bytes, accounts: Accounts, storage: Storage) -> Optional[Account]:
    # 1. get account details hash
    # 2. resolve storage objects to get account details
    # 3. return account
    return None

# Example of instantiation:
#
# Assuming you have an instance of Storage (e.g., from your storage module), you can create
# an Accounts instance either as an empty trie or using an existing root hash:
#
#   storage = Storage()
#
#   # To instantiate an empty Accounts trie:
#   accounts = Accounts(storage)
#
#   # To instantiate with an existing trie root hash:
#   existing_root_hash = b'...'  # This would be loaded from persistent storage.
#   accounts = Accounts(storage, root_hash=existing_root_hash)
