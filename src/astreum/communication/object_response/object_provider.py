import socket
from typing import Tuple


def decode_object_provider(payload: bytes) -> Tuple[bytes, str, int]:
    expected_len = 32 + 4 + 2
    if len(payload) < expected_len:
        raise ValueError("provider payload too short")

    provider_public_key = payload[:32]
    provider_ip_bytes = payload[32:36]
    provider_port_bytes = payload[36:38]

    provider_address = socket.inet_ntoa(provider_ip_bytes)
    provider_port = int.from_bytes(provider_port_bytes, byteorder="big", signed=False)
    return provider_public_key, provider_address, provider_port
