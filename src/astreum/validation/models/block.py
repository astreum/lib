
from typing import Any, List, Optional, TYPE_CHECKING

from ...machine.models.expression import Expr, resolve_list_exprs
from ...machine.models.expression import ZERO32
from .accounts import Accounts

if TYPE_CHECKING:
    from ...storage.models.trie import Trie
    from ...consensus.transaction.model import Transaction
    from ...consensus.transaction.storage.pending import PendingStorageContract
    from ...crypto.bloom_tree import BloomTree


class Block:
    """Validation Block representation using Expr storage.

    The block header Expr chain:

      chain: body --[Link]--> sig --[Link]--> ver --[Link]--> terminal Symbol("block")

    Details order in body_list (alphabetical by field name):
      0: accounts_hash              (Link head_hash)
      1: bloom_hash                 (Link head_hash)
      2: chain_id                   (Expr.Int)
      3: cumulative_burn            (Expr.Int)
      4: cumulative_mint            (Expr.Int)
      5: cumulative_stake           (Expr.Int)
      6: cumulative_storage_fee     (Expr.Int)
      7: cumulative_transaction_fee (Expr.Int)
      8: difficulty                 (Expr.Int)
      9: height                     (Expr.Int)
      10: nonce                      (Expr.Int)
      11: previous_block_hash        (Link head_hash)
      12: previous_era_hash          (Link head_hash)
      13: receipts_hash              (Link head_hash)
      14: timestamp                  (Expr.Int)
      15: total_storage_fee          (Expr.Int)
      16: total_transaction_fee      (Expr.Int)
      17: transactions_hash          (Link head_hash)
      18: validator_public_key_bytes (Expr.Bytes)

    Notes:
      - "body tree" is represented here by the body_list id (self.body_hash), not
        embedded again as a field to avoid circular references.
      - "signature" is a field on the class but is not required for validation
        navigation; include it in the instance but it is not encoded in atoms
        unless explicitly provided via details extension in the future.
    """

    version: int
    expr_id: Optional[bytes]
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
    receipts_trie: Optional["Trie"]
    pending_exprs: List[Expr]
    pending_storage_contracts: List["PendingStorageContract"]
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
        expr_id: Optional[bytes] = None,
        body_hash: Optional[bytes] = None,
        accounts: Optional["Trie"] = None,
        transactions: Optional[List["Transaction"]] = None,
        receipts: Optional[List["Receipt"]] = None,
        receipts_trie: Optional["Trie"] = None,
        pending_exprs: Optional[List[Expr]] = None,
        pending_storage_contracts: Optional[List["PendingStorageContract"]] = None,
    ) -> None:
        self.version = int(version)
        self.expr_id = expr_id
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
        self.receipts_trie = receipts_trie
        self.pending_exprs = list(pending_exprs or [])
        self.pending_storage_contracts = list(pending_storage_contracts or [])
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
        if not isinstance(ver, Expr.Int):
            raise ValueError("invalid block version: expected Int")
        version = ver.value
        if version != 1:
            raise ValueError(f"unsupported block version (version={version})")
        if not isinstance(body, Expr.Link):
            raise ValueError("block body must be a Link chain")

        body_nodes, missed = resolve_list_exprs(node, body)
        if missed:
            raise ValueError(
                f"unable to resolve block body (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(body_nodes) != 19:
            raise ValueError(
                f"malformed block body length (got={len(body_nodes)}, expected=19)"
            )

        (
            accounts_node,
            bloom_hash_node,
            chain_id_node,
            cumulative_burn_node,
            cumulative_mint_node,
            cumulative_stake_node,
            cumulative_storage_fee_node,
            cumulative_transaction_fee_node,
            difficulty_node,
            height_node,
            nonce_node,
            prev_node,
            previous_era_hash_node,
            receipts_node,
            timestamp_node,
            total_storage_fee_node,
            total_transaction_fee_node,
            transactions_node,
            validator_node,
        ) = body_nodes

        if not isinstance(accounts_node, Expr.Link):
            raise ValueError("expected Link for accounts_hash")
        if not isinstance(bloom_hash_node, Expr.Link):
            raise ValueError("expected Link for bloom_hash")
        if not isinstance(chain_id_node, Expr.Int):
            raise ValueError("expected Int for chain_id")
        if not isinstance(cumulative_burn_node, Expr.Int):
            raise ValueError("expected Int for cumulative_burn")
        if not isinstance(cumulative_mint_node, Expr.Int):
            raise ValueError("expected Int for cumulative_mint")
        if not isinstance(cumulative_stake_node, Expr.Int):
            raise ValueError("expected Int for cumulative_stake")
        if not isinstance(cumulative_storage_fee_node, Expr.Int):
            raise ValueError("expected Int for cumulative_storage_fee")
        if not isinstance(cumulative_transaction_fee_node, Expr.Int):
            raise ValueError("expected Int for cumulative_transaction_fee")
        if not isinstance(difficulty_node, Expr.Int):
            raise ValueError("expected Int for difficulty")
        if not isinstance(height_node, Expr.Int):
            raise ValueError("expected Int for height")
        if not isinstance(nonce_node, Expr.Int):
            raise ValueError("expected Int for nonce")
        if not isinstance(prev_node, Expr.Link):
            raise ValueError("expected Link for previous_block_hash")
        if not isinstance(previous_era_hash_node, Expr.Link):
            raise ValueError("expected Link for previous_era_hash")
        if not isinstance(receipts_node, Expr.Link):
            raise ValueError("expected Link for receipts_hash")
        if not isinstance(timestamp_node, Expr.Int):
            raise ValueError("expected Int for timestamp")
        if not isinstance(total_storage_fee_node, Expr.Int):
            raise ValueError("expected Int for total_storage_fee")
        if not isinstance(total_transaction_fee_node, Expr.Int):
            raise ValueError("expected Int for total_transaction_fee")
        if not isinstance(transactions_node, Expr.Link):
            raise ValueError("expected Link for transactions_hash")
        if not isinstance(validator_node, Expr.Bytes):
            raise ValueError("expected Bytes for validator_public_key_bytes")

        block = cls(
            version=version,
            chain_id=chain_id_node.value,
            previous_block_hash=prev_node.head_hash if prev_node.head_hash is not None else ZERO32,
            previous_block=None,
            height=height_node.value,
            timestamp=timestamp_node.value,
            accounts_hash=accounts_node.head_hash or None,
            total_transaction_fee=total_transaction_fee_node.value,
            total_storage_fee=total_storage_fee_node.value,
            cumulative_transaction_fee=cumulative_transaction_fee_node.value,
            cumulative_storage_fee=cumulative_storage_fee_node.value,
            cumulative_stake=cumulative_stake_node.value,
            cumulative_burn=cumulative_burn_node.value,
            cumulative_mint=cumulative_mint_node.value,
            transactions_hash=transactions_node.head_hash or None,
            receipts_hash=receipts_node.head_hash or None,
            difficulty=difficulty_node.value,
            validator_public_key_bytes=validator_node.value or None,
            nonce=nonce_node.value,
            bloom_hash=bloom_hash_node.head_hash or None,
            previous_era_hash=previous_era_hash_node.head_hash or None,
            signature=signature_bytes,
            expr_id=block_id,
            body_hash=body.hash(),
        )

        # Populate bloom_tree from stored bloom_hash
        from ...crypto.bloom_tree import BloomTree
        block.bloom_tree = BloomTree(block.bloom_hash, node)

        return block

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        # Build Link chain from innermost to outermost (alphabetical field order).
        # resolve_list_exprs flattens this to accounts_hash..validator.
        body: Expr = Expr.Bytes(self.validator_public_key_bytes or b"")
        body = Expr.Link(Expr.Link(head_hash=self.transactions_hash or b""), body)
        body = Expr.Link(Expr.Int(self.total_transaction_fee), body)
        body = Expr.Link(Expr.Int(self.total_storage_fee), body)
        body = Expr.Link(Expr.Int(self.timestamp), body)
        body = Expr.Link(Expr.Link(head_hash=self.receipts_hash or b""), body)
        body = Expr.Link(Expr.Link(head_hash=self.previous_era_hash or ZERO32), body)
        body = Expr.Link(Expr.Link(head_hash=self.previous_block_hash), body)
        body = Expr.Link(Expr.Int(self.nonce or 0), body)
        body = Expr.Link(Expr.Int(self.height), body)
        body = Expr.Link(Expr.Int(self.difficulty), body)
        body = Expr.Link(Expr.Int(self.cumulative_transaction_fee), body)
        body = Expr.Link(Expr.Int(self.cumulative_storage_fee), body)
        body = Expr.Link(Expr.Int(self.cumulative_stake), body)
        body = Expr.Link(Expr.Int(self.cumulative_mint), body)
        body = Expr.Link(Expr.Int(self.cumulative_burn), body)
        body = Expr.Link(Expr.Int(self.chain_id), body)
        body = Expr.Link(Expr.Link(head_hash=self.bloom_hash or ZERO32), body)
        body = Expr.Link(Expr.Link(head_hash=self.accounts_hash or b""), body)
        self.body_hash = body.hash()
        expr: Expr = Expr.Link(
            body,
            Expr.Link(
                Expr.Bytes(self.signature or b""),
                Expr.Link(
                    Expr.Int(self.version),
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
            self._expr = None
            block_hash = self.expr().hash()
            leading_zeros = self._leading_zero_bits(block_hash)
            if leading_zeros >= target:
                self.expr_id = block_hash
                return nonce
            nonce += 1
