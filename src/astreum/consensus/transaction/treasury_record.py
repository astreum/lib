from __future__ import annotations

from dataclasses import dataclass

from ...storage.models.atom import Atom, ZERO32, bytes_list_to_atoms
from ...utils.integer import int_to_bytes


@dataclass(frozen=True)
class TreasuryUserRecord:
    stake_balance: int = 0
    loans_root_hash: bytes = ZERO32
    total_interest_paid: int = 0


def encode_treasury_user_record(record: TreasuryUserRecord) -> tuple[bytes, list[Atom]]:
    loans_root_hash = bytes(record.loans_root_hash or ZERO32)
    if len(loans_root_hash) != len(ZERO32):
        raise ValueError("loans_root_hash must be 32 bytes")
    if record.stake_balance < 0:
        raise ValueError("stake_balance must be non-negative")
    if record.total_interest_paid < 0:
        raise ValueError("total_interest_paid must be non-negative")

    return bytes_list_to_atoms(
        [
            int_to_bytes(record.stake_balance),
            loans_root_hash,
            int_to_bytes(record.total_interest_paid),
        ]
    )
