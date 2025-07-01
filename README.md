# lib

Python library to interact with the Astreum blockchain and its Lispeum virtual machine.

[View on PyPI](https://pypi.org/project/astreum/)

## Configuration

When initializing an `astreum.Node`, pass a dictionary with any of the options below. Only the parameters you want to override need to be present – everything else falls back to its default.

### Core Configuration

| Parameter                   | Type       | Default        | Description                                                                                                                                                                      |
| --------------------------- | ---------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `machine-only`              | bool       | `True`         | When **True** the node starts in *machine‑only* mode: no storage subsystem and no relay networking – only the Lispeum VM. Set to **False** to enable storage and relay features. |
| `relay_secret_key`          | hex string | Auto‑generated | Ed25519 private key that identifies the node on the network. If omitted, a fresh keypair is generated and kept in‑memory.                                                        |
| `validation_secret_key`     | hex string | `None`         | X25519 private key that lets the node participate in the validation route. Leave unset for a non‑validator node.                                                                 |
| `storage_path`              | string     | `None`         | Directory where objects are persisted. If *None*, the node uses an in‑memory store.                                                                                              |
| `storage_get_relay_timeout` | float      | `5`            | Seconds to wait for an object requested from peers before timing‑out.                                                                                                            |

### Networking

| Parameter       | Type                    | Default | Description                                                                         |
| --------------- | ----------------------- | ------- | ----------------------------------------------------------------------------------- |
| `use_ipv6`      | bool                    | `False` | Listen on IPv6 as well as IPv4.                                                     |
| `incoming_port` | int                     | `7373`  | UDP port the relay binds to.                                                        |
| `bootstrap`     | list\[tuple\[str, int]] | `[]`    | Initial peers used to join the network, e.g. `[ ("bootstrap.astreum.org", 7373) ]`. |

> **Note**
> The peer‑to‑peer *route* used for object discovery is always enabled.
> If `validation_secret_key` is provided the node automatically joins the validation route too.

### Example

```python
from astreum.node import Node

config = {
    "machine-only": False,                   # run full node
    "relay_secret_key": "ab…cd",             # optional – hex encoded
    "validation_secret_key": "12…34",        # optional – validator
    "storage_path": "./data/node1",
    "storage_get_relay_timeout": 5,
    "incoming_port": 7373,
    "use_ipv6": False,
    "bootstrap": [
        ("bootstrap.astreum.org", 7373),
        ("127.0.0.1", 7374)
    ]
}

node = Node(config)
# … your code …
```

## Lispeum Machine Quickstart

The Lispeum virtual machine (VM) is embedded inside `astreum.Node`. You feed it Lispeum source text, and the node tokenizes, parses, and **evaluates** the resulting AST inside an isolated environment.

```python
from astreum.node import Node
from astreum.machine.tokenizer import tokenize
from astreum.machine.parser import parse

# 1. Spin‑up a stand‑alone VM (machine‑only node).
node = Node({"machine-only": True})

# 2. Create an environment.
env_id = node.machine_create_environment()

# 3. Convert Lispeum source → Expr AST.
source = '(+ 1 (* 2 3))'
expr, _ = parse(tokenize(source))

# 4. Evaluate
result = node.machine_expr_eval(env_id=env_id, expr=expr)  # -> Expr.Integer(7)

print(result.value)  # 7
```

### Handling errors

Both helpers raise `ParseError` (from `astreum.machine.error`) when something goes wrong:

* Unterminated string literals are caught by `tokenize`.
* Unexpected or missing parentheses are caught by `parse`.

Catch the exception to provide developer‑friendly diagnostics:

```python
try:
    tokens = tokenize(bad_source)
    expr, _ = parse(tokens)
except ParseError as e:
    print("Parse failed:", e)
```

---

## Testing

```bash

python3 -m unittest discover -s tests
```
