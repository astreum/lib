# lib

Python library to interact with the Astreum blockchain and its Lispeum virtual machine.

[View on PyPI](https://pypi.org/project/astreum/)

## Configuration

When initializing an Astreum Node, you need to provide a configuration dictionary. Below are the available configuration parameters:

### Node Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_id` | bytes | Random 32 bytes | Unique identifier for the node |
| `followed_chain_id` | bytes | None | ID of the blockchain that this node follows |
| `storage_path` | str | "./storage" | Directory path where node data will be stored |

### Network Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_ipv6` | bool | False | Whether to use IPv6 (True) or IPv4 (False) |
| `incoming_port` | int | 7373 | Port to listen for incoming messages |
| `max_message_size` | int | 65536 | Maximum size of UDP datagrams in bytes |
| `num_workers` | int | 4 | Number of worker threads for message processing |

### Route Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `peer_route` | bool | False | Whether to participate in the peer discovery route |
| `validation_route` | bool | False | Whether to participate in the block validation route |
| `bootstrap_peers` | list | [] | List of bootstrap peers in the format `[("hostname", port), ...]` |

### Example Usage

```python
from astreum.node import Node

# Configuration dictionary
config = {
    "node_id": b"my-unique-node-id-goes-here-exactly-32",  # 32 bytes
    "followed_chain_id": b"main-chain-id-goes-here",
    "storage_path": "./data/node1",
    "incoming_port": 7373,
    "use_ipv6": False,
    "peer_route": True,
    "validation_route": True,
    "bootstrap_peers": [
        ("bootstrap.astreum.org", 7373),
        ("127.0.0.1", 7374)
    ]
}

# Initialize the node with config
node = Node(config)

# Start the node
node.start()

# ... use the node ...

# Stop the node when done
node.stop()
```

## Testing

python3 -m unittest discover -s tests
