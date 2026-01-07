from __future__ import annotations

from typing import Optional



def provider_id_for_payload(node, payload: bytes) -> int:
    """Return the provider id for a payload, inserting if new."""
    for idx, existing in enumerate(node.storage_providers):
        if existing == payload:
            return idx
    node.storage_providers.append(payload)
    return len(node.storage_providers) - 1



def provider_payload_for_id(node, provider_id: int) -> Optional[bytes]:
    """Return the provider payload for a provider id, or None."""
    if not isinstance(provider_id, int) or provider_id < 0:
        return None
    try:
        return node.storage_providers[provider_id]
    except IndexError:
        return None
