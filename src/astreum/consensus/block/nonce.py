from astreum.consensus.models.block import Block
from astreum.consensus.block.encoding.expr import get_block_expr
from astreum.consensus.block.utils.bits import count_leading_zero_bits


def generate_block_nonce(
    *,
    block: Block,
    difficulty: int,
) -> int:
    """Search for a nonce that satisfies the proof-of-work difficulty target.

    Mutates the block in place — sets ``block.nonce`` through the search
    range, clears ``block._expr`` each iteration so the expression is
    recomputed, and stores the winning hash in ``block.expr_id``.

    Args:
        block: The block to mine a nonce for.
        difficulty: Minimum number of leading zero bits required in the
            block hash.

    Returns:
        The nonce that satisfies the target.
    """
    target = max(1, difficulty)
    start = block.nonce or 0
    nonce = start
    while True:
        block.nonce = nonce
        block._expr = None
        block_hash = get_block_expr(block).hash()
        leading_zeros = count_leading_zero_bits(block_hash)
        if leading_zeros >= target:
            block.expr_id = block_hash
            return nonce
        nonce += 1
