
from typing import Any, List, Optional, TYPE_CHECKING

from ...machine.models.expression import Expr, resolve_list_exprs
from ...machine.models.expression import ZERO32
from .accounts import Accounts

if TYPE_CHECKING:
    from ...storage.models.trie import Trie
    from ...consensus.transaction.model import Transaction
    from ...crypto.bloom_tree import BloomTree

def _be_bytes_to_int(b: Optional[bytes]) -> int:
    if not b:
        return 0
    return int.from_bytes(b, "big")


def _int_to_be_bytes(value: int | None) -> bytes:
    if value is None:
        return b""
    value = int(value)
    if value == 0:
        return b"\x00"
    size = (value.bit_length() + 7) // 8
    return value.to_bytes(size, "big")


class Block:
    """Validation Block representation using Expr storage.

    The block header Expr chain:

      chain: body --[Link]--> sig --[Link]--> ver --[Link]--> terminal Symbol("block")

    Details order in body_list:
      0: chain_id                            (byte)
      1: height                              (int -> big-endian bytes)
      2: previous_block_hash                 (bytes)
      3: timestamp                           (int -> big-endian bytes)
      4: difficulty                          (int -> big-endian bytes)
      5: cumulative_stake                    (int -> big-endian bytes)
      6: cumulative_burn                     (int -> big-endian bytes)
      7: cumulative_mint                     (int -> big-endian bytes)
      8: cumulative_transaction_fee          (int -> big-endian bytes)
      9: cumulative_storage_fee              (int -> big-endian bytes)
      10: total_transaction_fee              (int -> big-endian bytes)
      11: total_storage_fee                  (int -> big-endian bytes)
      12: accounts_hash                      (bytes)
      13: transactions_hash                  (bytes)
      14: receipts_hash                      (bytes)
      15: validator_public_key_bytes         (bytes)
      16: bloom_hash                         (Link head_hash)
      17: previous_era_hash                  (Link head_hash)
      18: nonce                              (int -> big-endian bytes)

    Notes:
      - "body tree" is represented here by the body_list id (self.body_hash), not
        embedded again as a field to avoid circular references.
      - "signature" is a field on the class but is not required for validation
        navigation; include it in the instance but it is not encoded in atoms
        unless explicitly provided via details extension in the future.
    """

    version: int
    atom_hash: Optional[bytes]
    chain_id: int
    previous_block_hash: bytes
    previous_block: Optional["Block"]

    # block details
    height: int
    timestamp: Optional[int]
    accounts_hash: Optional[bytes]
    total_transaction_fee: Optional[int]
    total_storage_fee: Optional[int]
    cumulative_transaction_fee: Optional[int]
    cumulative_storage_fee: Optional[int]
    cumulative_stake: Optional[int]
    cumulative_burn: Optional[int]
    cumulative_mint: Optional[int]
    transactions_hash: Optional[bytes]
    receipts_hash: Optional[bytes]
    difficulty: Optional[int]
    validator_public_key_bytes: Optional[bytes]
    nonce: Optional[int]
    bloom_hash: Optional[bytes]
    previous_era_hash: Optional[bytes]

    # additional
    body_hash: Optional[bytes]
    signature: Optional[bytes]
    total_mint: int

    # structures
    accounts: Optional["Trie"]
    transactions: Optional[List["Transaction"]]
    receipts: Optional[List["Receipt"]]
    pending_exprs: List[Expr]
    bloom_tree: Optional["BloomTree"]  # current era tree
    _expr: Optional["Expr"]
    
    def __init__(
        self,
        *,
        chain_id: int,
        previous_block_hash: bytes,
        previous_block: Optional["Block"],
        height: int,
        timestamp: Optional[int],
        accounts_hash: Optional[bytes],
        total_transaction_fee: Optional[int],
        total_storage_fee: Optional[int],
        cumulative_transaction_fee: Optional[int],
        cumulative_storage_fee: Optional[int],
        cumulative_stake: Optional[int],
        cumulative_burn: Optional[int],
        cumulative_mint: Optional[int],
        transactions_hash: Optional[bytes],
        receipts_hash: Optional[bytes],
        difficulty: Optional[int],
        validator_public_key_bytes: Optional[bytes],
        version: int = 1,
        nonce: Optional[int] = None,
        bloom_hash: Optional[bytes] = None,
        previous_era_hash: Optional[bytes] = None,
        signature: Optional[bytes] = None,
        total_mint: int = 0,
        atom_hash: Optional[bytes] = None,
        body_hash: Optional[bytes] = None,
        accounts: Optional["Trie"] = None,
        transactions: Optional[List["Transaction"]] = None,
        receipts: Optional[List["Receipt"]] = None,
        pending_exprs: Optional[List[Expr]] = None,
    ) -> None:
        self.version = int(version)
        self.atom_hash = atom_hash
        self.chain_id = chain_id
        self.previous_block_hash = previous_block_hash
        self.previous_block = previous_block
        self.height = height
        self.timestamp = timestamp
        self.accounts_hash = accounts_hash
        self.total_transaction_fee = total_transaction_fee
        self.total_storage_fee = total_storage_fee
        self.cumulative_transaction_fee = cumulative_transaction_fee
        self.cumulative_storage_fee = cumulative_storage_fee
        self.cumulative_stake = cumulative_stake
        self.cumulative_burn = cumulative_burn
        self.cumulative_mint = cumulative_mint
        self.transactions_hash = transactions_hash
        self.receipts_hash = receipts_hash
        self.difficulty = difficulty
        self.validator_public_key_bytes = (
            bytes(validator_public_key_bytes) if validator_public_key_bytes else None
        )
        self.nonce = nonce
        self.bloom_hash = bloom_hash
        self.previous_era_hash = previous_era_hash
        self.body_hash = body_hash
        self.signature = signature
        self.total_mint = int(total_mint)
        if accounts is None and accounts_hash:
            self.accounts = Accounts(root_hash=accounts_hash)
        else:
            self.accounts = accounts
        self.transactions = transactions
        self.receipts = receipts
        self.pending_exprs = list(pending_exprs or [])
        self.bloom_tree = None
        self._expr = None

    @property
    def total_fee(self) -> int:
        return int(self.total_transaction_fee or 0) + int(self.total_storage_fee or 0)

    @property
    def cumulative_total_fee(self) -> int:
        return int(self.cumulative_transaction_fee or 0) + int(self.cumulative_storage_fee or 0)

    @classmethod
    def from_storage(cls, node: Any, block_id: bytes) -> "Block":

        header = node.get_expr_list(block_id)
        if header is None:
            raise ValueError("unable to load block header from storage")
        if not isinstance(header, Expr.Link):
            raise ValueError("block header must be a Link")

        header_nodes, missed = resolve_list_exprs(node, header)
        if missed:
            raise ValueError(
                f"unable to resolve block header (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(header_nodes) != 4:
            raise ValueError(
                f"malformed block header length (got={len(header_nodes)}, expected=4)"
            )

        body, sig, ver, terminal = header_nodes
        if not isinstance(terminal, Expr.Symbol) or terminal.value != "block":
            raise ValueError(
                f"invalid block header terminal (expected Symbol('block'), got {terminal!r})"
            )
        if not isinstance(sig, Expr.Bytes):
            raise ValueError("invalid block signature: expected Bytes")
        signature_bytes = sig.value
        if not isinstance(ver, Expr.Bytes):
            raise ValueError("invalid block version: expected Bytes")
        version = _be_bytes_to_int(ver.value)
        if version != 1:
            raise ValueError(f"unsupported block version (version={version})")
        if not isinstance(body, Expr.Link):
            raise ValueError("block body must be a Link chain")

        body_nodes, missed = resolve_list_exprs(node, body)
        if missed:
            raise ValueError(
                f"unable to resolve block body (missed={[h.hex()[:8] for h in missed]})"
            )
        detail_values: list[bytes] = []
        for n in body_nodes:
            if isinstance(n, Expr.Bytes):
                detail_values.append(n.value)
            elif isinstance(n, Expr.Link):
                detail_values.append(n.head_hash if n.head_hash is not None else n.hash())
            else:
                raise ValueError(f"unexpected block body node type: {type(n).__name__}")
        if len(detail_values) != 19:
            raise ValueError(
                f"malformed block body length (got={len(detail_values)}, expected=19)"
            )

        (
            chain_bytes,
            height_bytes,
            prev_bytes,
            timestamp_bytes,
            difficulty_bytes,
            cumulative_stake_bytes,
            cumulative_burn_bytes,
            cumulative_mint_bytes,
            cumulative_transaction_fee_bytes,
            cumulative_storage_fee_bytes,
            total_transaction_fee_bytes,
            total_storage_fee_bytes,
            accounts_bytes,
            transactions_bytes,
            receipts_bytes,
            validator_bytes,
            bloom_hash_bytes,
            previous_era_hash_bytes,
            nonce_bytes,
        ) = detail_values

        block = cls(
            version=version,
            chain_id=_be_bytes_to_int(chain_bytes),
            previous_block_hash=prev_bytes or ZERO32,
            previous_block=None,
            height=_be_bytes_to_int(height_bytes),
            timestamp=_be_bytes_to_int(timestamp_bytes),
            accounts_hash=accounts_bytes or None,
            total_transaction_fee=_be_bytes_to_int(total_transaction_fee_bytes),
            total_storage_fee=_be_bytes_to_int(total_storage_fee_bytes),
            cumulative_transaction_fee=_be_bytes_to_int(cumulative_transaction_fee_bytes),
            cumulative_storage_fee=_be_bytes_to_int(cumulative_storage_fee_bytes),
            cumulative_stake=_be_bytes_to_int(cumulative_stake_bytes),
            cumulative_burn=_be_bytes_to_int(cumulative_burn_bytes),
            cumulative_mint=_be_bytes_to_int(cumulative_mint_bytes),
            transactions_hash=transactions_bytes or None,
            receipts_hash=receipts_bytes or None,
            difficulty=_be_bytes_to_int(difficulty_bytes),
            validator_public_key_bytes=validator_bytes or None,
            nonce=_be_bytes_to_int(nonce_bytes),
            bloom_hash=bloom_hash_bytes or None,
            previous_era_hash=previous_era_hash_bytes or None,
            signature=signature_bytes,
            atom_hash=block_id,
            body_hash=body.hash(),
        )

        # Populate bloom_tree from stored bloom_hash
        if block.bloom_hash and block.bloom_hash != ZERO32:
            bloom_expr = node.get_expr(block.bloom_hash)
            if bloom_expr is not None:
                from ...crypto.bloom_tree import BloomTree
                from ...crypto.bloom_tree.expr import bloom_node_from_expr
                root = bloom_node_from_expr(bloom_expr)
                era = BloomTree()
                era.root = root
                block.bloom_tree = era

        return block

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        body: Expr = Expr.Bytes(_int_to_be_bytes(self.nonce or 0))
        body = Expr.Link(Expr.Link(head_hash=self.previous_era_hash or ZERO32), body)
        body = Expr.Link(Expr.Link(head_hash=self.bloom_hash or ZERO32), body)
        body = Expr.Link(Expr.Bytes(self.validator_public_key_bytes or b""), body)
        body = Expr.Link(Expr.Link(head_hash=self.receipts_hash or b""), body)
        body = Expr.Link(Expr.Link(head_hash=self.transactions_hash or b""), body)
        body = Expr.Link(Expr.Link(head_hash=self.accounts_hash or b""), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.total_storage_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.total_transaction_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.cumulative_storage_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.cumulative_transaction_fee)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.cumulative_mint)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.cumulative_burn)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.cumulative_stake)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.difficulty)), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.timestamp)), body)
        body = Expr.Link(Expr.Link(head_hash=self.previous_block_hash), body)
        body = Expr.Link(Expr.Bytes(_int_to_be_bytes(self.height)), body)
        body = Expr.Link(
            Expr.Bytes(_int_to_be_bytes(self.chain_id)), body)
        self.body_hash = body.hash()
        expr: Expr = Expr.Link(
            body,
            Expr.Link(
                Expr.Bytes(self.signature or b""),
                Expr.Link(
                    Expr.Bytes(_int_to_be_bytes(self.version)),
                    Expr.Symbol("block"))))
        return expr

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

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
            block_hash = self.expr().hash()
            leading_zeros = self._leading_zero_bits(block_hash)
            if leading_zeros >= target:
                self.atom_hash = block_hash
                return nonce
            nonce += 1
