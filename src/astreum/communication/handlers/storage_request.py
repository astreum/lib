from __future__ import annotations

from typing import TYPE_CHECKING, Sequence

from cryptography.hazmat.primitives import serialization

if TYPE_CHECKING:
    from .... import Node
    from ..models.message import Message


def handle_storage_request(node: "Node", addr: Sequence[object], message: "Message") -> None:
    """Process incoming storage request payloads, forwarding if needed."""
    logger = node.logger
    payload = message.content
    if len(payload) < 32:
        return

    atom_id = payload[:32]
    provider_bytes = payload[32:]
    if not provider_bytes:
        return

    try:
        provider_str = provider_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return

    try:
        host, port = addr[0], int(addr[1])
    except Exception:
        return
    address_key = (host, port)
    sender_key_bytes = node.addresses.get(address_key)
    if sender_key_bytes is None:
        return

    try:
        local_key_bytes = node.relay_public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    except Exception:
        return

    def xor_distance(target: bytes, key: bytes) -> int:
        return int.from_bytes(
            bytes(a ^ b for a, b in zip(target, key)),
            byteorder="big",
            signed=False,
        )

    self_distance = xor_distance(atom_id, local_key_bytes)

    try:
        closest_peer = node.peer_route.closest_peer_for_hash(atom_id)
    except Exception:
        closest_peer = None

    if closest_peer is not None and closest_peer.public_key_bytes != sender_key_bytes:
        closest_distance = xor_distance(atom_id, closest_peer.public_key_bytes)
        if closest_distance < self_distance:
            target_addr = closest_peer.address
            if target_addr is not None and target_addr != addr:
                try:
                    node.outgoing_queue.put((message.to_bytes(), target_addr))
                except Exception:
                    return
                logger.debug(
                    "Forwarded storage request for %s to %s",
                    atom_id.hex(),
                    target_addr,
                )
                return

    node.storage_index[atom_id] = provider_str.strip()
    logger.debug(
        "Stored provider %s for atom %s",
        provider_str.strip(),
        atom_id.hex(),
    )
