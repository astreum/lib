from ..format import encode, decode
from ..crypto import ed25519
import blake3

class Block:
    def __init__(
        self,
        number: int,
        prev_block_hash: bytes,
        timestamp: int,
        accounts_hash: bytes,
        transactions_total_fees: int,
        transaction_limit: int,
        transactions_root_hash: bytes,
        vdf_difficulty: int,
        vdf_output: bytes,
        vdf_proof: bytes,
        validator_pk: bytes,
        signature: bytes,
    ) -> None:
        self.accounts_hash = accounts_hash
        self.number = int(number)
        self.prev_block_hash = prev_block_hash
        self.timestamp = int(timestamp)
        self.transactions_total_fees = int(transactions_total_fees)
        self.transaction_limit = int(transaction_limit)
        self.transactions_root_hash = transactions_root_hash
        self.validator_pk = validator_pk
        self.vdf_difficulty = int(vdf_difficulty)
        self.vdf_output = vdf_output
        self.vdf_proof = vdf_proof
        self.signature = signature
        self.body_hash = self._compute_body_hash()

    def _body_fields_without_sig(self) -> list:
        return [
            self.accounts_hash,
            self.number,
            self.prev_block_hash,
            self.timestamp,
            self.transactions_total_fees,
            self.transaction_limit,
            self.transactions_root_hash,
            self.validator_pk,
            self.vdf_difficulty,
            self.vdf_output,
            self.vdf_proof,
        ]

    def _compute_body_hash(self) -> bytes:
        return blake3.blake3(encode(self._body_fields_without_sig())).digest()
    
    def to_bytes(self) -> bytes:
        return encode(self._body_fields_without_sig() + [self.signature])

    @classmethod
    def from_bytes(cls, blob: bytes) -> "Block":
        (
            accounts_hash,
            number,
            prev_block_hash,
            timestamp,
            transactions_total_fees,
            transaction_limit,
            transactions_root_hash,
            validator_pk,
            vdf_difficulty,
            vdf_output,
            vdf_proof,
            signature
        ) = decode(blob)
        return cls(
            number=int(number),
            prev_block_hash=prev_block_hash,
            timestamp=int(timestamp),
            accounts_hash=accounts_hash,
            transactions_total_fees=int(transactions_total_fees),
            transaction_limit=int(transaction_limit),
            transactions_root_hash=transactions_root_hash,
            vdf_difficulty=int(vdf_difficulty),
            vdf_output=vdf_output,
            vdf_proof=vdf_proof,
            validator_pk=validator_pk,
            signature=signature,
        )

    @property
    def hash(self) -> bytes:
        return blake3.blake3(self.body_hash + self.signature).digest()

    def verify_block_signature(self) -> bool:
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(self.validator_pk)
            pub.verify(self.signature, self.body_hash)
            return True
        except Exception:
            return False
  