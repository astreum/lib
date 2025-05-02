class Block:

    def __init__(self):
        pass
    
    @classmethod
    def from_bytes(cls) -> 'Block':
        """
        Deserialize a block from its byte representation.
    """
        return cls()

    def to_bytes(self) -> bytes:
        """
        Serialize the block into bytes.
        """
        return b""

class Chain:
    def __init__(self, latest_block: Block):
        self.latest_block = latest_block