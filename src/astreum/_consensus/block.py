
from typing import Any, Callable, List, Optional, Tuple, TYPE_CHECKING

from .._storage.atom import Atom, ZERO32

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


def _make_list(child_ids: List[bytes]) -> Tuple[bytes, List[Atom]]:
    """Create a typed 'list' atom for child object ids.

    Encodes elements as a linked chain of element-atoms with data=child_id and
    next pointing to the next element's object id. The list value atom contains
    the element count and points to the head of the element chain. The type atom
    identifies the structure as a list.
    """
    acc: List[Atom] = []
    next_hash = ZERO32
    elem_atoms: List[Atom] = []
    # Build element chain in reverse, then flip to maintain forward order
    for h in reversed(child_ids):
        a = Atom.from_data(data=h, next_hash=next_hash)
        next_hash = a.object_id()
        elem_atoms.append(a)
    elem_atoms.reverse()
    head = next_hash
    val = Atom.from_data(data=(len(child_ids)).to_bytes(8, "little"), next_hash=head)
    typ = Atom.from_data(data=b"list", next_hash=val.object_id())
    return typ.object_id(), acc + elem_atoms + [val, typ]


class Block:
    """Validation Block representation using Atom storage.

    Top-level encoding:
      block_id = list([ type_atom, body_list, signature_atom ])
      where: type_atom      = Atom(data=b"block", next=body_list_id)
             body_list      = list([...details...])
             signature_atom = Atom(data=<signature-bytes>)

    Details order in body_list:
      0: previous_block_hash                 (bytes)
      1: number                              (int → big-endian bytes)
      2: timestamp                           (int → big-endian bytes)
      3: accounts_hash                       (bytes)
      4: transactions_total_fees             (int → big-endian bytes)
      5: transactions_hash                   (bytes)
      6: receipts_hash                       (bytes)
      7: delay_difficulty                    (int → big-endian bytes)
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
        atoms_acc: List[Atom] = []

        def _emit(detail_bytes: bytes) -> None:
            atom = Atom.from_data(data=detail_bytes)
            details_ids.append(atom.object_id())
            atoms_acc.append(atom)

        # 0: previous_block_hash
        prev_hash = self.previous_block_hash or (self.previous_block.hash if self.previous_block else b"")
        prev_hash = prev_hash or ZERO32
        self.previous_block_hash = prev_hash
        _emit(prev_hash)
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

        # Build body list
        body_id, body_atoms = _make_list(details_ids)
        atoms_acc.extend(body_atoms)
        self.body_hash = body_id

        # Type atom points to body list
        type_atom = Atom.from_data(data=b"block", next_hash=body_id)

        # Signature atom (raw byte payload)
        sig_atom = Atom.from_data(data=self.signature or b"", next_hash=ZERO32)

        # Main block list: [type_atom, body_list, signature]
        main_id, main_atoms = _make_list([type_atom.object_id(), body_id, sig_atom.object_id()])
        atoms_acc.append(type_atom)
        atoms_acc.append(sig_atom)
        atoms_acc.extend(main_atoms)

        self.hash = main_id
        return self.hash, atoms_acc

    @classmethod
    def from_atom(cls, source: Any, block_id: bytes) -> "Block":
        storage_get: Optional[Callable[[bytes], Optional[Atom]]]
        if callable(source):
            storage_get = source
        else:
            storage_get = getattr(source, "_local_get", None)
        if not callable(storage_get):
            raise TypeError("Block.from_atom requires a node with '_local_get' or a callable storage getter")
        # 1) Expect main list
        main_typ = storage_get(block_id)
        if main_typ is None or main_typ.data != b"list":
            raise ValueError("not a block (main list missing)")
        main_val = storage_get(main_typ.next)
        if main_val is None:
            raise ValueError("malformed block list (missing value)")
        # length is little-endian u64 per storage format
        if len(main_val.data) < 1:
            raise ValueError("malformed block list (length)")
        head = main_val.next

        # read first 2 elements: [type_atom_id, body_list_id]
        first_elem = storage_get(head)
        if first_elem is None:
            raise ValueError("malformed block list (head element)")
        type_atom_id = first_elem.data
        second_elem = storage_get(first_elem.next)
        if second_elem is None:
            raise ValueError("malformed block list (second element)")
        body_list_id = second_elem.data
        # optional 3rd element: signature atom id
        third_elem = storage_get(second_elem.next) if second_elem.next else None
        sig_atom_id: Optional[bytes] = third_elem.data if third_elem is not None else None

        # 2) Validate type atom and linkage to body
        type_atom = storage_get(type_atom_id)
        if type_atom is None or type_atom.data != b"block" or type_atom.next != body_list_id:
            raise ValueError("not a block (type atom)")

        # 3) Parse body list of details
        body_typ = storage_get(body_list_id)
        if body_typ is None or body_typ.data != b"list":
            raise ValueError("malformed body (type)")
        body_val = storage_get(body_typ.next)
        if body_val is None:
            raise ValueError("malformed body (value)")
        cur_elem_id = body_val.next

        def _read_detail_bytes(elem_id: bytes) -> bytes:
            elem = storage_get(elem_id)
            if elem is None:
                return b""
            child_id = elem.data
            detail = storage_get(child_id)
            return detail.data if detail is not None else b""

        details: List[bytes] = []
        # We read up to 10 fields if present
        for _ in range(10):
            if not cur_elem_id:
                break
            b = _read_detail_bytes(cur_elem_id)
            details.append(b)
            nxt = storage_get(cur_elem_id)
            cur_elem_id = nxt.next if nxt is not None else b""

        b = cls()
        b.hash = block_id
        b.body_hash = body_list_id

        # Map details back per the defined order
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

        # 4) Parse signature if present (supports raw or typed 'bytes' atom)
        if sig_atom_id is not None:
            sa = storage_get(sig_atom_id)
            if sa is not None:
                if sa.data == b"bytes":
                    sval = storage_get(sa.next)
                    b.signature = sval.data if sval is not None else b""
                else:
                    b.signature = sa.data

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
