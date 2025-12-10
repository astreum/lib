from typing import Tuple


def address_str_to_host_and_port(address: str) -> Tuple[str, int]:
    """Parse `host:port` (or `[ipv6]:port`) into a tuple."""
    addr = address.strip()
    if not addr:
        raise ValueError("address cannot be empty")

    host: str
    port_str: str

    if addr.startswith('['):
        end = addr.find(']')
        if end == -1:
            raise ValueError("missing closing ']' in IPv6 address")
        host = addr[1:end]
        remainder = addr[end + 1 :]
        if not remainder.startswith(':'):
            raise ValueError("missing port separator after IPv6 address")
        port_str = remainder[1:]
    else:
        if ':' not in addr:
            raise ValueError("address must contain ':' separating host and port")
        host, port_str = addr.rsplit(':', 1)

    host = host.strip()
    if not host:
        raise ValueError("host cannot be empty")
    port_str = port_str.strip()
    if not port_str:
        raise ValueError("port cannot be empty")

    try:
        port = int(port_str, 10)
    except ValueError as exc:
        raise ValueError(f"invalid port number: {port_str}") from exc

    if not (0 < port < 65536):
        raise ValueError(f"port out of range: {port}")

    return host, port


def xor_distance(a: bytes, b: bytes) -> int:
    """Return the unsigned integer XOR distance between two equal-length identifiers."""
    if len(a) != len(b):
        raise ValueError("xor distance requires operands of equal length")
    return int.from_bytes(bytes(x ^ y for x, y in zip(a, b)), "big", signed=False)
