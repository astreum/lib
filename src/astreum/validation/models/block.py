
from typing import Any, List, Optional, TYPE_CHECKING

from ...machine.models.expression import Expr, resolve_list_exprs, link, int_, bytes_, symbol
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
      2: chain_id                   (int_)
      3: cumulative_burn            (int_)
      4: cumulative_mint            (int_)
      5: cumulative_stake           (int_)
      6: cumulative_storage_fee     (int_)
      7: cumulative_transaction_fee (int_)
      8: difficulty                 (int_)
      9: height                     (int_)
      10: nonce                      (int_)
      11: previous_block_hash        (Link head_hash)
      12: previous_era_hash          (Link head_hash)
      13: receipts_hash              (Link head_hash)
      14: timestamp                  (int_)
      15: total_storage_fee          (int_)
      16: total_transaction_fee      (int_)
      17: transactions_hash          (Link head_hash)
      18: validator_public_key_bytes (bytes_)

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
    pending_bloom_keys: set[bytes]
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
        self.pending_bloom_keys = set()
        self._expr = None

    def snapshot(self) -> tuple:
        """Capture revertible mutable state (accounts cache, pending exprs,
        pending storage contracts, total_mint). Returns an opaque tuple."""
        saved_cache = {
            addr: acct.clone()
            for addr, acct in self.accounts._cache.items()
        }
        saved_pending_exprs = list(self.pending_exprs)
        saved_pending_storage = list(self.pending_storage_contracts)
        saved_total_mint = int(self.total_mint)
        return (saved_cache, saved_pending_exprs, saved_pending_storage, saved_total_mint)

    def restore(self, snapshot: tuple) -> None:
        """Revert mutable state to a prior snapshot."""
        saved_cache, saved_pending_exprs, saved_pending_storage, saved_total_mint = snapshot
        self.accounts._cache = saved_cache
        self.pending_exprs = saved_pending_exprs
        self.pending_storage_contracts = saved_pending_storage
        self.total_mint = saved_total_mint

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
        if not header._tag == "link":
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
        if not terminal._tag == "symbol" or terminal.value != "block":
            raise ValueError(
                f"invalid block header terminal (expected Symbol('block'), got {terminal!r})"
            )
        if not sig._tag == "bytes":
            raise ValueError("invalid block signature: expected Bytes")
        signature_bytes = sig.value
        if not ver._tag == "int":
            raise ValueError("invalid block version: expected Int")
        version = ver.value
        if version != 1:
            raise ValueError(f"unsupported block version (version={version})")
        if not body._tag == "link":
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

        if not accounts_node._tag == "link":
            raise ValueError("expected Link for accounts_hash")
        if not bloom_hash_node._tag == "link":
            raise ValueError("expected Link for bloom_hash")
        if not chain_id_node._tag == "int":
            raise ValueError("expected Int for chain_id")
        if not cumulative_burn_node._tag == "int":
            raise ValueError("expected Int for cumulative_burn")
        if not cumulative_mint_node._tag == "int":
            raise ValueError("expected Int for cumulative_mint")
        if not cumulative_stake_node._tag == "int":
            raise ValueError("expected Int for cumulative_stake")
        if not cumulative_storage_fee_node._tag == "int":
            raise ValueError("expected Int for cumulative_storage_fee")
        if not cumulative_transaction_fee_node._tag == "int":
            raise ValueError("expected Int for cumulative_transaction_fee")
        if not difficulty_node._tag == "int":
            raise ValueError("expected Int for difficulty")
        if not height_node._tag == "int":
            raise ValueError("expected Int for height")
        if not nonce_node._tag == "int":
            raise ValueError("expected Int for nonce")
        if not prev_node._tag == "link":
            raise ValueError("expected Link for previous_block_hash")
        if not previous_era_hash_node._tag == "link":
            raise ValueError("expected Link for previous_era_hash")
        if not receipts_node._tag == "link":
            raise ValueError("expected Link for receipts_hash")
        if not timestamp_node._tag == "int":
            raise ValueError("expected Int for timestamp")
        if not total_storage_fee_node._tag == "int":
            raise ValueError("expected Int for total_storage_fee")
        if not total_transaction_fee_node._tag == "int":
            raise ValueError("expected Int for total_transaction_fee")
        if not transactions_node._tag == "link":
            raise ValueError("expected Link for transactions_hash")
        if not validator_node._tag == "bytes":
            raise ValueError("expected Bytes for validator_public_key_bytes")

        block = cls(
            version=version,
            chain_id=chain_id_node.value,
            previous_block_hash=prev_node._head_hash if prev_node._head_hash is not None else ZERO32,
            previous_block=None,
            height=height_node.value,
            timestamp=timestamp_node.value,
            accounts_hash=accounts_node._head_hash or None,
            total_transaction_fee=total_transaction_fee_node.value,
            total_storage_fee=total_storage_fee_node.value,
            cumulative_transaction_fee=cumulative_transaction_fee_node.value,
            cumulative_storage_fee=cumulative_storage_fee_node.value,
            cumulative_stake=cumulative_stake_node.value,
            cumulative_burn=cumulative_burn_node.value,
            cumulative_mint=cumulative_mint_node.value,
            transactions_hash=transactions_node._head_hash or None,
            receipts_hash=receipts_node._head_hash or None,
            difficulty=difficulty_node.value,
            validator_public_key_bytes=validator_node.value or None,
            nonce=nonce_node.value,
            bloom_hash=bloom_hash_node._head_hash or None,
            previous_era_hash=previous_era_hash_node._head_hash or None,
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
        body: Expr = bytes_(self.validator_public_key_bytes or b"")
        body = link(Expr("link", head_hash=self.transactions_hash or b""), body)
        body = link(int_(self.total_transaction_fee), body)
        body = link(int_(self.total_storage_fee), body)
        body = link(int_(self.timestamp), body)
        body = link(Expr("link", head_hash=self.receipts_hash or b""), body)
        body = link(Expr("link", head_hash=self.previous_era_hash or ZERO32), body)
        body = link(Expr("link", head_hash=self.previous_block_hash), body)
        body = link(int_(self.nonce or 0), body)
        body = link(int_(self.height), body)
        body = link(int_(self.difficulty), body)
        body = link(int_(self.cumulative_transaction_fee), body)
        body = link(int_(self.cumulative_storage_fee), body)
        body = link(int_(self.cumulative_stake), body)
        body = link(int_(self.cumulative_mint), body)
        body = link(int_(self.cumulative_burn), body)
        body = link(int_(self.chain_id), body)
        body = link(Expr("link", head_hash=self.bloom_hash or ZERO32), body)
        body = link(Expr("link", head_hash=self.accounts_hash or b""), body)
        self.body_hash = body.hash()
        expr: Expr = link(
            body,
            link(
                bytes_(self.signature or b""),
                link(
                    int_(self.version),
                    symbol("block"))))
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
