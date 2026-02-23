from __future__ import annotations


def calculate_iaar(block: object) -> float:
    """Calculate IAAR (Inflation Adjusted Astreum Rate) from the previous block.

    IAAR is defined as:
    (cumulative transaction fee + cumulative storage fee - cumulative mint)
    / cumulative stake

    All cumulative values are taken from ``block.previous_block``.
    """
    previous_block = block.previous_block
    if previous_block is None:
        raise ValueError("block.previous_block is required to calculate iaar")

    cumulative_total_fee = int(previous_block.cumulative_total_fee)
    cumulative_mint = int(previous_block.cumulative_mint)
    numerator = cumulative_total_fee - cumulative_mint
    denominator = int(previous_block.cumulative_stake)
    if denominator <= 0:
        raise ValueError("previous block cumulative_stake must be greater than zero")

    return numerator / denominator


def calculate_storage_fee(block: object, total_bytes: int) -> int:
    """Calculate inflation-adjusted storage fee from the previous block."""
    previous_block = block.previous_block
    if previous_block is None:
        raise ValueError("block.previous_block is required to calculate storage fees")

    numerator = int(total_bytes) * int(previous_block.cumulative_stake)
    denominator = int(previous_block.cumulative_total_fee) - int(previous_block.cumulative_mint)
    if denominator <= 0:
        raise ValueError("previous block net cumulative fees must be greater than zero")

    return (numerator + denominator - 1) // denominator
