
from typing import Any, List, Optional, TYPE_CHECKING

from astreum.expression import Expr, NIL, resolve_list_exprs, link, int_, bytes_, symbol
from astreum.expression import ZERO32
from astreum.storage.get.list import get_expr_list
from astreum.consensus.models.accounts import Accounts

if TYPE_CHECKING:
    from astreum.storage.radix import RadixTree
    from astreum.consensus.transaction.model import Transaction
    from astreum.consensus.transaction.storage.pending import PendingStorageContract
    from astreum.crypto.bloom_tree import BloomTree


class Block:
    version: int
    expr_id: Optional[bytes]
    chain_id: int
    previous_block_hash: bytes
    previous_block: Optional["Block"]

    height: int
    timestamp: Optional[int]
    accounts_hash: Optional[bytes]
    total_transaction_fee: Optional[int]
    total_storage_fee: Optional[int]
    transactions_hash: Optional[bytes]
    receipts_hash: Optional[bytes]
    difficulty: Optional[int]
    validator_public_key_bytes: Optional[bytes]
    nonce: Optional[int]
    bloom_hash: Optional[bytes]
    previous_era_hash: Optional[bytes]

    body_hash: Optional[bytes]
    signature: Optional[bytes]
    total_mint: int

    accounts: Optional["RadixTree"]
    transactions: Optional[List["Transaction"]]
    receipts: Optional[List["Receipt"]]
    receipts_trie: Optional["RadixTree"]
    statistics: Optional[list]
    pending_exprs: List[Expr]
    pending_storage_contracts: List["PendingStorageContract"]
    bloom_tree: Optional["BloomTree"]
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
        accounts: Optional["RadixTree"] = None,
        transactions: Optional[List["Transaction"]] = None,
        receipts: Optional[List["Receipt"]] = None,
        receipts_trie: Optional["RadixTree"] = None,
        statistics: Optional[list] = None,
        pending_exprs: Optional[List[Expr]] = None,
        pending_storage_contracts: Optional[List["PendingStorageContract"]] = None,
    ) -> None:
        self.version = version
        self.expr_id = expr_id
        self.chain_id = chain_id
        self.previous_block_hash = previous_block_hash
        self.previous_block = previous_block
        self.height = height
        self.timestamp = timestamp
        self.accounts_hash = accounts_hash
        self.total_transaction_fee = total_transaction_fee
        self.total_storage_fee = total_storage_fee
        self.transactions_hash = transactions_hash
        self.receipts_hash = receipts_hash
        self.difficulty = difficulty
        self.validator_public_key_bytes = (
            validator_public_key_bytes if validator_public_key_bytes else None
        )
        self.nonce = nonce
        self.bloom_hash = bloom_hash
        self.previous_era_hash = previous_era_hash
        self.body_hash = body_hash
        self.signature = signature
        self.total_mint = total_mint
        if accounts is None and accounts_hash:
            self.accounts = Accounts(root_hash=accounts_hash)
        else:
            self.accounts = accounts
        self.transactions = transactions
        self.receipts = receipts
        self.receipts_trie = receipts_trie
        self.pending_exprs = list(pending_exprs or [])
        self.statistics = statistics or []
        self.pending_storage_contracts = list(pending_storage_contracts or [])
        self.bloom_tree = None
        self.pending_bloom_keys = set()
        self._expr = None

    def snapshot(self) -> tuple:
        saved_cache = {
            addr: acct.clone()
            for addr, acct in self.accounts._cache.items()
        }
        saved_pending_exprs = list(self.pending_exprs)
        saved_pending_storage = list(self.pending_storage_contracts)
        saved_total_mint = self.total_mint
        return (saved_cache, saved_pending_exprs, saved_pending_storage, saved_total_mint)

    def restore(self, snapshot: tuple) -> None:
        saved_cache, saved_pending_exprs, saved_pending_storage, saved_total_mint = snapshot
        self.accounts._cache = saved_cache
        self.pending_exprs = saved_pending_exprs
        self.pending_storage_contracts = saved_pending_storage
        self.total_mint = saved_total_mint

    @property
    def total_fee(self) -> int:
        return (self.total_transaction_fee or 0) + (self.total_storage_fee or 0)

    @property
    def cumulative_total_fee(self) -> int:
        if self.statistics:
            return self.statistics[0][0]
        return 0

    @property
    def cumulative_stake(self) -> int:
        if self.statistics:
            return self.statistics[0][1]
        return 0

    @classmethod
    def from_storage(cls, node: Any, block_id: bytes) -> "Block":

        header = get_expr_list(node, block_id)
        if header is None:
            raise ValueError("unable to load block header from storage")
        if not header._tag == "link":
            raise ValueError("block header must be a Link")
        if header._tail is None or header._tail._tag != "symbol" or header._tail.value != "block":
            raise ValueError(
                f"invalid block type tag (got {header._tail!r})"
            )

        inner = header._head
        if inner is None or inner._tag != "link":
            raise ValueError("block inner header must be a Link")

        inner_nodes, missed = resolve_list_exprs(node, inner)
        if missed:
            raise ValueError(
                f"unable to resolve block header (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(inner_nodes) != 2:
            raise ValueError(
                f"malformed block header length (got={len(inner_nodes)}, expected=2)"
            )

        body, sig = inner_nodes
        if not sig._tag == "bytes":
            raise ValueError("invalid block signature: expected Bytes")
        signature_bytes = sig.value
        if not body._tag == "link":
            raise ValueError("block body must be a Link chain")

        body_nodes, missed = resolve_list_exprs(node, body)
        if missed:
            raise ValueError(
                f"unable to resolve block body (missed={[h.hex()[:8] for h in missed]})"
            )
        if len(body_nodes) != 16:
            raise ValueError(
                f"malformed block body length (got={len(body_nodes)}, expected=16)"
            )

        (
            version_node,
            accounts_node,
            bloom_hash_node,
            chain_id_node,
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
            statistics_node,
        ) = body_nodes

        if not version_node._tag == "int":
            raise ValueError("expected Int for version")
        version = version_node.value
        if version != 1:
            raise ValueError(f"unsupported block version (version={version})")
        if not accounts_node._tag == "link":
            raise ValueError("expected Link for accounts_hash")
        if not bloom_hash_node._tag == "link":
            raise ValueError("expected Link for bloom_hash")
        if not chain_id_node._tag == "int":
            raise ValueError("expected Int for chain_id")
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

        if statistics_node._tag == "link":
            stat_nodes, missed = resolve_list_exprs(node, statistics_node)
            if missed:
                raise ValueError(
                    f"unable to resolve statistics (missed={[h.hex()[:8] for h in missed]})"
                )
            statistics = []
            for j, entry_node in enumerate(stat_nodes):
                int_nodes, missed = resolve_list_exprs(node, entry_node)
                if missed:
                    raise ValueError(
                        f"unable to resolve statistics entry {j} (missed={[h.hex()[:8] for h in missed]})"
                    )
                if j == 0 and len(int_nodes) == 2:
                    statistics.append((int_nodes[0].value, int_nodes[1].value, 0, 0))
                elif len(int_nodes) == 4:
                    statistics.append((int_nodes[0].value, int_nodes[1].value, int_nodes[2].value, int_nodes[3].value))
                else:
                    raise ValueError(
                        f"invalid statistics entry {j} length (got={len(int_nodes)})"
                    )
        elif statistics_node._tag == "symbol":
            statistics = []
        else:
            raise ValueError("expected Link or Symbol for statistics")

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
            statistics=statistics,
        )

        from astreum.crypto.bloom_tree import BloomTree
        block.bloom_tree = BloomTree(block.bloom_hash, node)

        return block

    @staticmethod
    def _statistics_to_expr(statistics: list | None) -> Expr:
        if not statistics:
            return NIL
        expr = NIL
        for i in range(len(statistics) - 1, -1, -1):
            if i == 0:
                fee, stake, _, _ = statistics[i]
                entry = link(int_(fee), link(int_(stake), NIL))
            else:
                pf, ps, cf, cs = statistics[i]
                entry = link(int_(pf), link(int_(ps), link(int_(cf), link(int_(cs), NIL))))
            expr = link(entry, expr)
        return expr

    def to_expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        body: Expr = link(self._statistics_to_expr(self.statistics), NIL)
        body = link(bytes_(self.validator_public_key_bytes or b""), body)
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
        body = link(int_(self.chain_id), body)
        body = link(Expr("link", head_hash=self.bloom_hash or ZERO32), body)
        body = link(Expr("link", head_hash=self.accounts_hash or b""), body)
        body = link(int_(self.version), body)
        self.body_hash = body.hash()
        expr: Expr = link(
            link(body, link(bytes_(self.signature or b""), NIL)),
            symbol("block"))
        return expr

    def expr(self) -> Expr:
        if self._expr is not None:
            return self._expr
        self._expr = self.to_expr()
        return self._expr

    @staticmethod
    def _leading_zero_bits(buf: bytes) -> int:
        zeros = 0
        for byte in buf:
            if byte == 0:
                zeros += 8
                continue
            zeros += 8 - byte.bit_length()
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
        base_difficulty = max(1, previous_difficulty or 1)
        if previous_timestamp is None or current_timestamp is None:
            return base_difficulty

        spacing = max(0, current_timestamp - previous_timestamp)
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
        target = max(1, difficulty)
        start = self.nonce or 0
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
