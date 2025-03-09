# lib

Python library to interact with the Astreum blockchain and its Lispeum virtual machine.

[View on PyPI](https://pypi.org/project/astreum/)

## Configuration

When initializing an Astreum Node, you need to provide a configuration dictionary. Below are the available configuration parameters:

### Node Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `private_key` | string | Auto-generated | Hex string of Ed25519 private key. If not provided, a new keypair will be generated automatically |
| `storage_path` | string | "storage" | Path to store data |
| `max_storage_space` | int | 1073741824 (1GB) | Maximum storage space in bytes |
| `max_object_recursion` | int | 50 | Maximum recursion depth for resolving nested objects |

### Network Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `use_ipv6` | bool | False | Whether to use IPv6 (True) or IPv4 (False) |
| `incoming_port` | int | 7373 | Port to listen for incoming messages |
| `max_message_size` | int | 65536 | Maximum size of UDP datagrams in bytes |
| `num_workers` | int | 4 | Number of worker threads for message processing |
| `network_request_timeout` | float | 5.0 | Maximum time (in seconds) to wait for network object requests |

### Route Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `validation_route` | bool | False | Whether to participate in the block validation route |
| `bootstrap_peers` | list | [] | List of bootstrap peers in the format `[("hostname", port), ...]` |

> **Note:** The peer route is always enabled as it's necessary for object discovery and retrieval.

### Example Usage

```python
from astreum.node import Node

# Configuration dictionary
config = {
    "private_key": "my-private-key-goes-here",
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
