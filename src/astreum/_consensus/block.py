
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING

from .._storage.atom import Atom, AtomKind, ZERO32

if TYPE_CHECKING:
    from .._storage.patricia import PatriciaTrie
    from .transaction import Transaction
    from .receipt import Receipt
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.exceptions import InvalidSignature


def _int_to_be_bytes(n: Optional[int]) -> bytes:
    if n is None:
        return b""
    n = int(n)
    if n == 0:
        return b"\x00"
    size = (n.bit_length() + 7) // 8
    return n.to_bytes(size, "big")


def _be_bytes_to_int(b: Optional[bytes]) -> int:
    if not b:
        return 0
    return int.from_bytes(b, "big")


class Block:
    """Validation Block representation using Atom storage.

    Top-level encoding:
      block_id = type_atom.object_id()
      chain: type_atom --next--> signature_atom --next--> body_list_atom --next--> ZERO32
      where: type_atom        = Atom(kind=AtomKind.SYMBOL, data=b"block")
             signature_atom   = Atom(kind=AtomKind.BYTES, data=<signature-bytes>)
             body_list_atom   = Atom(kind=AtomKind.LIST,  data=<body_head_id>)

    Details order in body_list:
      0: previous_block_hash                 (bytes)
      1: number                              (int -> big-endian bytes)
      2: timestamp                           (int -> big-endian bytes)
      3: accounts_hash                       (bytes)
      4: transactions_total_fees             (int -> big-endian bytes)
      5: transactions_hash                   (bytes)
      6: receipts_hash                       (bytes)
      7: delay_difficulty                    (int -> big-endian bytes)
      8: delay_output                        (bytes)
      9: validator_public_key                (bytes)

    Notes:
      - "body tree" is represented here by the body_list id (self.body_hash), not
        embedded again as a field to avoid circular references.
      - "signature" is a field on the class but is not required for validation
        navigation; include it in the instance but it is not encoded in atoms
        unless explicitly provided via details extension in the future.
    """

    # essential identifiers
    hash: bytes
    previous_block_hash: bytes
    previous_block: Optional["Block"]

    # block details
    number: Optional[int]
    timestamp: Optional[int]
    accounts_hash: Optional[bytes]
    transactions_total_fees: Optional[int]
    transactions_hash: Optional[bytes]
    receipts_hash: Optional[bytes]
    delay_difficulty: Optional[int]
    delay_output: Optional[bytes]
    validator_public_key: Optional[bytes]

    # additional
    body_hash: Optional[bytes]
    signature: Optional[bytes]

    # structures
    accounts: Optional["PatriciaTrie"]
    transactions: Optional[List["Transaction"]]
    receipts: Optional[List["Receipt"]]
    
    

    def __init__(self) -> None:
        # defaults for safety
        self.hash = b""
        self.previous_block_hash = ZERO32
        self.previous_block = None
        self.number = None
        self.timestamp = None
        self.accounts_hash = None
        self.transactions_total_fees = None
        self.transactions_hash = None
        self.receipts_hash = None
        self.delay_difficulty = None
        self.delay_output = None
        self.validator_public_key = None
        self.body_hash = None
        self.signature = None
        self.accounts = None
        self.transactions = None
        self.receipts = None

    def to_atom(self) -> Tuple[bytes, List[Atom]]:
        # Build body details as direct byte atoms, in defined order
        details_ids: List[bytes] = []
        block_atoms: List[Atom] = []

        def _emit(detail_bytes: bytes) -> None:
            atom = Atom.from_data(data=detail_bytes, kind=AtomKind.BYTES)
            details_ids.append(atom.object_id())
            block_atoms.append(atom)

        # 0: previous_block_hash
        _emit(self.previous_block_hash)
        # 1: number
        _emit(_int_to_be_bytes(self.number))
        # 2: timestamp
        _emit(_int_to_be_bytes(self.timestamp))
        # 3: accounts_hash
        _emit(self.accounts_hash or b"")
        # 4: transactions_total_fees
        _emit(_int_to_be_bytes(self.transactions_total_fees))
        # 5: transactions_hash
        _emit(self.transactions_hash or b"")
        # 6: receipts_hash
        _emit(self.receipts_hash or b"")
        # 7: delay_difficulty
        _emit(_int_to_be_bytes(self.delay_difficulty))
        # 8: delay_output
        _emit(self.delay_output or b"")
        # 9: validator_public_key
        _emit(self.validator_public_key or b"")

        # Build body list chain (head points to the first detail atom id)
        body_atoms: List[Atom] = []
        body_head = ZERO32
        for child_id in reversed(details_ids):
            node = Atom.from_data(data=child_id, next_hash=body_head, kind=AtomKind.BYTES)
            body_head = node.object_id()
            body_atoms.append(node)
        body_atoms.reverse()

        block_atoms.extend(body_atoms)

        body_list_atom = Atom.from_data(data=body_head, kind=AtomKind.LIST)
        self.body_hash = body_list_atom.object_id()

        # Signature atom links to body list atom; type atom links to signature atom
        sig_atom = Atom.from_data(data=self.signature, next_hash=self.body_hash, kind=AtomKind.BYTES)
        type_atom = Atom.from_data(data=b"block", next_hash=sig_atom.object_id(), kind=AtomKind.SYMBOL)

        block_atoms.append(body_list_atom)
        block_atoms.append(sig_atom)
        block_atoms.append(type_atom)

        self.hash = type_atom.object_id()
        return self.hash, block_atoms

    @classmethod
    def from_atom(cls, source: Any, block_id: bytes) -> "Block":
        storage_get: Optional[Callable[[bytes], Optional[Atom]]]
        if callable(source):
            storage_get = source
        else:
            storage_get = getattr(source, "storage_get", None)
        if not callable(storage_get):
            raise TypeError(
                "Block.from_atom requires a node with 'storage_get' or a callable storage getter"
            )

        def _atom_kind(atom: Optional[Atom]) -> Optional[AtomKind]:
            kind_value = getattr(atom, "kind", None)
            if isinstance(kind_value, AtomKind):
                return kind_value
            if isinstance(kind_value, int):
                try:
                    return AtomKind(kind_value)
                except ValueError:
                    return None
            return None

        def _require_atom(atom_id: Optional[bytes], context: str, expected_kind: Optional[AtomKind] = None) -> Atom:
            if not atom_id or atom_id == ZERO32:
                raise ValueError(f"missing {context}")
            atom = storage_get(atom_id)
            if atom is None:
                raise ValueError(f"missing {context}")
            if expected_kind is not None:
                kind = _atom_kind(atom)
                if kind is not expected_kind:
                    raise ValueError(f"malformed {context}")
            return atom

        def _read_list(head_id: Optional[bytes], context: str) -> List[bytes]:
            entries: List[bytes] = []
            current = head_id
            if not current or current == ZERO32:
                return entries
            while current and current != ZERO32:
                node = storage_get(current)
                if node is None:
                    raise ValueError(f"missing list node while decoding {context}")
                node_kind = _atom_kind(node)
                if node_kind is not AtomKind.BYTES:
                    raise ValueError(f"list element must be bytes while decoding {context}")
                if len(node.data) != len(ZERO32):
                    raise ValueError(f"list element payload has unexpected length while decoding {context}")
                entries.append(node.data)
                current = node.next
            return entries

        type_atom = _require_atom(block_id, "block type atom", AtomKind.SYMBOL)
        if type_atom.data != b"block":
            raise ValueError("not a block (type atom payload)")

        sig_atom = _require_atom(type_atom.next, "block signature atom", AtomKind.BYTES)
        body_list_id = sig_atom.next
        body_list_atom = _require_atom(body_list_id, "block body list atom", AtomKind.LIST)
        if body_list_atom.next and body_list_atom.next != ZERO32:
            raise ValueError("malformed block (body list tail)")

        body_child_ids = _read_list(body_list_atom.data, "block body")

        details: List[bytes] = []
        for idx, child_id in enumerate(body_child_ids):
            if idx >= 10:
                break
            if not child_id or child_id == ZERO32:
                details.append(b"")
                continue
            detail_atom = storage_get(child_id)
            details.append(detail_atom.data if detail_atom is not None else b"")

        if len(details) < 10:
            details.extend([b""] * (10 - len(details)))

        b = cls()
        b.hash = block_id
        b.body_hash = body_list_id

        get = lambda i: details[i] if i < len(details) else b""
        b.previous_block_hash = get(0) or ZERO32
        b.previous_block = None
        b.number = _be_bytes_to_int(get(1))
        b.timestamp = _be_bytes_to_int(get(2))
        b.accounts_hash = get(3) or None
        b.transactions_total_fees = _be_bytes_to_int(get(4))
        b.transactions_hash = get(5) or None
        b.receipts_hash = get(6) or None
        b.delay_difficulty = _be_bytes_to_int(get(7))
        b.delay_output = get(8) or None
        b.validator_public_key = get(9) or None

        b.signature = sig_atom.data if sig_atom is not None else None

        return b

    def validate(self, storage_get: Callable[[bytes], Optional[Atom]]) -> bool:
        """Validate this block against storage.

        Checks:
        - Signature: signature must verify over the body list id using the
          validator's public key.
        - Timestamp monotonicity: if previous block exists (not ZERO32), this
          block's timestamp must be >= previous.timestamp + 1.
        """
        # Unverifiable if critical fields are missing
        if not self.body_hash:
            return False
        if not self.signature:
            return False
        if not self.validator_public_key:
            return False
        if self.timestamp is None:
            return False

        # 1) Signature check over body hash
        try:
            pub = Ed25519PublicKey.from_public_bytes(bytes(self.validator_public_key))
            pub.verify(self.signature, self.body_hash)
        except InvalidSignature as e:
            raise ValueError("invalid signature") from e

        # 2) Timestamp monotonicity against previous block
        prev_ts: Optional[int] = None
        prev_hash = self.previous_block_hash or ZERO32

        if self.previous_block is not None:
            prev_ts = int(self.previous_block.timestamp or 0)
            prev_hash = self.previous_block.hash or prev_hash or ZERO32

        if prev_hash and prev_hash != ZERO32 and prev_ts is None:
            # If previous block cannot be loaded, treat as unverifiable, not malicious
            try:
                prev = Block.from_atom(storage_get, prev_hash)
            except Exception:
                return False
            prev_ts = int(prev.timestamp or 0)

        if prev_hash and prev_hash != ZERO32:
            if prev_ts is None:
                return False
            cur_ts = int(self.timestamp or 0)
            if cur_ts < prev_ts + 1:
                raise ValueError("timestamp must be at least prev+1")

        return True
