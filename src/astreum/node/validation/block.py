class Block:
    @classmethod
    def from_bytes(cls, validator) -> 'Block':
        """
        Deserialize an Account from its byte representation.
        
        Expected format: [balance, code, counter, data]
        
        The public_key (and optional secret_key) must be provided separately.
    """
        decoded = bytes_format.decode(data)
        balance, code, counter, account_data = decoded
        return cls(public_key, balance, code, counter, account_data, secret_key=secret_key)
    
    def to_bytes(self) -> bytes:
        """
        Serialize the Account into bytes.
        
        Format: [balance, code, counter, data]
        """
        return bytes_format.encode([
            self.balance,
            self.code,
            self.counter,
            self.data
        ])

class Chain:
    def __init__(self, latest_block: Block):
        self.latest_block = latest_block