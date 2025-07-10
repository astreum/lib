from ..format import encode, decode
from ..crypto import ed25519
import blake3

class Transaction:
    def __init__(
        self,
        sender_pk: bytes,
        recipient_pk: bytes,
        amount: int,
        fee: int,
        nonce: int,
        signature: bytes | None = None,
    ) -> None:
        self.sender_pk = sender_pk
        self.recipient_pk = recipient_pk
        self.amount = amount
        self.fee = fee
        self.nonce = nonce
        self.signature = signature

        if self.amount < 0 or self.fee < 0:
            raise ValueError("amount and fee must be non-negative")
        
        if self.fee % 2 != 0:
            raise ValueError("fee must be divisible by two")

        self.tx_body_hash: bytes = blake3.blake3(self._body_bytes()).digest()
        
        if self.signature is not None:
            self.tx_hash = blake3.blake3(self.tx_body_hash + self.signature).digest()
        else:
            self.tx_hash = None

    def sign(self, priv_key: ed25519.Ed25519PrivateKey) -> None:
        if self.signature is not None:
            raise ValueError("transaction already signed")
        sig = priv_key.sign(self.tx_body_hash)
        self.signature = sig
        self.tx_hash = blake3.blake3(self.tx_body_hash + sig).digest()

    def verify_signature(self) -> bool:
        if self.signature is None:
            return False
        try:
            pub = ed25519.Ed25519PublicKey.from_public_bytes(self.sender_pk)
            pub.verify(self.signature, self.tx_body_hash)
            return True
        except Exception:
            return False

    def to_bytes(self) -> bytes:
        sig = self.signature or b""
        return encode([
            self.sender_pk,
            self.recipient_pk,
            self.amount,
            self.fee,
            self.nonce,
            sig,
        ])

    @classmethod
    def from_bytes(cls, blob: bytes) -> 'Transaction':
        sender, recipient, amount, fee, nonce, sig = decode(blob)
        return cls(sender, recipient, int(amount), int(fee), int(nonce), sig)

    def _body_bytes(self) -> bytes:
        return encode([
            self.sender_pk,
            self.recipient_pk,
            self.amount,
            self.fee,
            self.nonce,
        ])

    def __eq__(self, other: "Transaction") -> bool:
        if not isinstance(other, Transaction):
            return NotImplemented
        return self.tx_hash == other.tx_hash

    def __hash__(self) -> int:
        return int.from_bytes(self.tx_hash, 'big')