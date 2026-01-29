
from typing import Any, List, Optional, Tuple, TYPE_CHECKING

from ...storage.models.atom import Atom, AtomKind, ZERO32
from .accounts import Accounts

if TYPE_CHECKING:
    from ...storage.models.trie import Trie
    from .transaction import Transaction

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
      chain: type_atom --next--> version_atom --next--> signature_atom --next--> body_list_atom --next--> ZERO32
      where: type_atom        = Atom(kind=AtomKind.SYMBOL, data=b"block")
             version_atom     = Atom(kind=AtomKind.BYTES,  data=b"\x01")
             signature_atom   = Atom(kind=AtomKind.BYTES, data=<signature-bytes>)
             body_list_atom   = Atom(kind=AtomKind.LIST,  data=<body_head_id>)

    Details order in body_list:
      0: chain_id                            (byte)
      1: height                              (int -> big-endian bytes)
      2: previous_block_hash                 (bytes)
      3: timestamp                           (int -> big-endian bytes)
      4: difficulty                          (int -> big-endian bytes)
      5: cumulative_stake                    (int -> big-endian bytes)
      6: cumulative_total_fees               (int -> big-endian bytes)
      7: total_fees                          (int -> big-endian bytes)
      8: accounts_hash                       (bytes)
      9: transactions_hash                   (bytes)
      10: receipts_hash                      (bytes)
      11: validator_public_key_bytes         (bytes)
      12: nonce                              (int -> big-endian bytes)

    Notes:
      - "body tree" is represented here by the body_list id (self.body_hash), not
        embedded again as a field to avoid circular references.
      - "signature" is a field on the class but is not required for validation
        navigation; include it in the instance but it is not encoded in atoms
        unless explicitly provided via details extension in the future.
    """

    # essential identifiers
    version: int
    atom_hash: Optional[bytes]
    chain_id: int
    previous_block_hash: bytes
    previous_block: Optional["Block"]

    # block details
    height: int
    timestamp: Optional[int]
    accounts_hash: Optional[bytes]
    total_fees: Optional[int]
    cumulative_total_fees: Optional[int]
    cumulative_stake: Optional[int]
    transactions_hash: Optional[bytes]
    receipts_hash: Optional[bytes]
    difficulty: Optional[int]
    validator_public_key_bytes: Optional[bytes]
    nonce: Optional[int]

    # additional
    body_hash: Optional[bytes]
    signature: Optional[bytes]

    # structures
    accounts: Optional["Trie"]
    transactions: Optional[List["Transaction"]]
    receipts: Optional[List["Receipt"]]
    
    def __init__(
        self,
        *,
        chain_id: int,
        previous_block_hash: bytes,
        previous_block: Optional["Block"],
        height: int,
        timestamp: Optional[int],
        accounts_hash: Optional[bytes],
        total_fees: Optional[int],
        cumulative_total_fees: Optional[int],
        cumulative_stake: Optional[int],
        transactions_hash: Optional[bytes],
        receipts_hash: Optional[bytes],
        difficulty: Optional[int],
        validator_public_key_bytes: Optional[bytes],
        version: int = 1,
        nonce: Optional[int] = None,
        signature: Optional[bytes] = None,
        atom_hash: Optional[bytes] = None,
        body_hash: Optional[bytes] = None,
        accounts: Optional["Trie"] = None,
        transactions: Optional[List["Transaction"]] = None,
        receipts: Optional[List["Receipt"]] = None,
    ) -> None:
        self.version = int(version)
        self.atom_hash = atom_hash
        self.chain_id = chain_id
        self.previous_block_hash = previous_block_hash
        self.previous_block = previous_block
        self.height = height
        self.timestamp = timestamp
        self.accounts_hash = accounts_hash
        self.total_fees = total_fees
        self.cumulative_total_fees = cumulative_total_fees
        self.cumulative_stake = cumulative_stake
        self.transactions_hash = transactions_hash
        self.receipts_hash = receipts_hash
        self.difficulty = difficulty
        self.validator_public_key_bytes = (
            bytes(validator_public_key_bytes) if validator_public_key_bytes else None
        )
        self.nonce = nonce
        self.body_hash = body_hash
        self.signature = signature
        if accounts is None and accounts_hash:
            self.accounts = Accounts(root_hash=accounts_hash)
        else:
            self.accounts = accounts
        self.transactions = transactions
        self.receipts = receipts

    def atomize(self) -> Tuple[bytes, List[Atom]]:
        # Build body details as direct byte atoms, in defined order
        detail_payloads: List[bytes] = []
        block_atoms: List[Atom] = []

        def _emit(detail_bytes: bytes) -> None:
            detail_payloads.append(detail_bytes)

        # 0: chain_id
        _emit(_int_to_be_bytes(self.chain_id))
        # 1: height
        _emit(_int_to_be_bytes(self.height))
        # 2: previous_block_hash
        _emit(self.previous_block_hash)
        # 3: timestamp
        _emit(_int_to_be_bytes(self.timestamp))
        # 4: difficulty
        _emit(_int_to_be_bytes(self.difficulty))
        # 5: cumulative_stake
        _emit(_int_to_be_bytes(self.cumulative_stake))
        # 6: cumulative_total_fees
        _emit(_int_to_be_bytes(self.cumulative_total_fees))
        # 7: total_fees
        _emit(_int_to_be_bytes(self.total_fees))
        # 8: accounts_hash
        _emit(self.accounts_hash or b"")
        # 9: transactions_hash
        _emit(self.transactions_hash or b"")
        # 10: receipts_hash
        _emit(self.receipts_hash or b"")
        # 11: validator_public_key_bytes
        _emit(self.validator_public_key_bytes or b"")
        # 12: nonce
        _emit(_int_to_be_bytes(self.nonce))

        # Build body list chain directly from detail atoms
        body_head = ZERO32
        detail_atoms: List[Atom] = []
        for payload in reversed(detail_payloads):
            atom = Atom(data=payload, next_id=body_head, kind=AtomKind.BYTES)
            detail_atoms.append(atom)
            body_head = atom.object_id()
        detail_atoms.reverse()

        block_atoms.extend(detail_atoms)

        body_list_atom = Atom(data=body_head, kind=AtomKind.LIST)
        self.body_hash = body_list_atom.object_id()

        # Signature atom links to body list atom; type atom links to signature atom
        sig_atom = Atom(
            data=bytes(self.signature or b""),
            next_id=self.body_hash,
            kind=AtomKind.BYTES,
        )
        version_atom = Atom(
            data=_int_to_be_bytes(self.version),
            next_id=sig_atom.object_id(),
            kind=AtomKind.BYTES,
        )
        type_atom = Atom(
            data=b"block",
            next_id=version_atom.object_id(),
            kind=AtomKind.SYMBOL,
        )

        block_atoms.append(body_list_atom)
        block_atoms.append(sig_atom)
        block_atoms.append(version_atom)
        block_atoms.append(type_atom)

        self.atom_hash = type_atom.object_id()
        return self.atom_hash, block_atoms

    @classmethod
    def from_storage(cls, node: Any, block_id: bytes) -> "Block":

        block_header = node.get_atom_list(block_id)
        if block_header is None:
            raise ValueError("unable to load block header list from storage")
        if len(block_header) != 4:
            raise ValueError(
                f"malformed block header list from storage (len={len(block_header)})"
            )
        type_atom, version_atom, sig_atom, body_list_atom = block_header

        if type_atom.kind is not AtomKind.SYMBOL or type_atom.data != b"block":
            raise ValueError(
                f"invalid block header type atom (kind={type_atom.kind}, data={type_atom.data!r})"
            )
        if version_atom.kind is not AtomKind.BYTES:
            raise ValueError(
                f"invalid block version atom kind (kind={version_atom.kind})"
            )
        version = _be_bytes_to_int(version_atom.data)
        if version != 1:
            raise ValueError(
                f"unsupported block version (version={version})"
            )
        if sig_atom.kind is not AtomKind.BYTES:
            raise ValueError(
                f"invalid block signature atom kind (kind={sig_atom.kind})"
            )
        if body_list_atom.kind is not AtomKind.LIST:
            raise ValueError(
                f"invalid block body list atom kind (kind={body_list_atom.kind})"
            )
        if body_list_atom.next_id != ZERO32:
            raise ValueError(
                f"invalid block body list tail (tail={body_list_atom.next_id.hex()})"
            )

        detail_atoms = node.get_atom_list(body_list_atom.data)
        if detail_atoms is None:
            raise ValueError("unable to load block body list from storage")

        if len(detail_atoms) != 13:
            raise ValueError(
                f"malformed block body list length (got={len(detail_atoms)}, expected=13)"
            )

        detail_values: List[bytes] = []
        for detail_atom in detail_atoms:
            if detail_atom.kind is not AtomKind.BYTES:
                raise ValueError(
                    f"invalid block body detail atom kind (kind={detail_atom.kind})"
                )
            detail_values.append(detail_atom.data)

        (
            chain_bytes,
            height_bytes,
            prev_bytes,
            timestamp_bytes,
            difficulty_bytes,
            cumulative_stake_bytes,
            cumulative_fees_bytes,
            fees_bytes,
            accounts_bytes,
            transactions_bytes,
            receipts_bytes,
            validator_bytes,
            nonce_bytes,
        ) = detail_values

        return cls(
            version=version,
            chain_id=_be_bytes_to_int(chain_bytes),
            previous_block_hash=prev_bytes or ZERO32,
            previous_block=None,
            height=_be_bytes_to_int(height_bytes),
            timestamp=_be_bytes_to_int(timestamp_bytes),
            accounts_hash=accounts_bytes or None,
            total_fees=_be_bytes_to_int(fees_bytes),
            cumulative_total_fees=_be_bytes_to_int(cumulative_fees_bytes),
            cumulative_stake=_be_bytes_to_int(cumulative_stake_bytes),
            transactions_hash=transactions_bytes or None,
            receipts_hash=receipts_bytes or None,
            difficulty=_be_bytes_to_int(difficulty_bytes),
            validator_public_key_bytes=validator_bytes or None,
            nonce=_be_bytes_to_int(nonce_bytes),
            signature=sig_atom.data if sig_atom is not None else None,
            atom_hash=block_id,
            body_hash=body_list_atom.object_id(),
        )

    @staticmethod
    def _leading_zero_bits(buf: bytes) -> int:
        """Return the number of leading zero bits in the provided buffer."""
        zeros = 0
        for byte in buf:
            if byte == 0:
                zeros += 8
                continue
            zeros += 8 - int(byte).bit_length()
            break
        return zeros

    @staticmethod
    def calculate_block_difficulty(
        *,
        previous_timestamp: Optional[int],
        current_timestamp: Optional[int],
        previous_difficulty: Optional[int],
        target_spacing: int = 2,
    ) -> int:
        """
        Adjust the delay difficulty with linear steps relative to block spacing.

        If blocks arrive too quickly (spacing <= 1), difficulty increases by one.
        If blocks are slower than the target spacing, difficulty decreases by one,
        and otherwise remains unchanged.
        """
        base_difficulty = max(1, int(previous_difficulty or 1))
        if previous_timestamp is None or current_timestamp is None:
            return base_difficulty

        spacing = max(0, int(current_timestamp) - int(previous_timestamp))
        if spacing <= 1:
            return base_difficulty + 1
        if spacing > target_spacing:
            return max(1, base_difficulty - 1)
        return base_difficulty

    def generate_nonce(
        self,
        *,
        difficulty: int,
    ) -> int:
        """
        Find a nonce that yields a block hash with the required leading zero bits.

        The search starts from the current nonce and iterates until the target
        difficulty is met.
        """
        target = max(1, int(difficulty))
        start = int(self.nonce or 0)
        nonce = start
        while True:
            self.nonce = nonce
            block_hash, _ = self.atomize()
            leading_zeros = self._leading_zero_bits(block_hash)
            if leading_zeros >= target:
                self.atom_hash = block_hash
                return nonce
            nonce += 1
