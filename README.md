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
# Define a named function int.add (stack body) and call it with bytes 1 and 2

import uuid
from astreum._node import Node, Env, Expr

# 1) Spin‑up a stand‑alone VM
node = Node()

# 2) Create an environment (simple manual setup)
env_id = uuid.uuid4()
node.environments[env_id] = Env()

# 3) Build a function value using a low‑level stack body via `sk`.
# Body does: $0 $1 add   (i.e., a + b)
low_body = Expr.ListExpr([
    Expr.Symbol("$0"),  # a (first arg)
    Expr.Symbol("$1"),  # b (second arg)
    Expr.Symbol("add"),
])

fn_body = Expr.ListExpr([
    Expr.Symbol("a"),
    Expr.Symbol("b"),
    Expr.ListExpr([low_body, Expr.Symbol("sk")]),
])

params = Expr.ListExpr([Expr.Symbol("a"), Expr.Symbol("b")])
int_add_fn = Expr.ListExpr([fn_body, params, Expr.Symbol("fn")])

# 4) Store under the name "int.add"
node.env_set(env_id, b"int.add", int_add_fn)

# 5) Retrieve the function and call it with bytes 1 and 2
bound = node.env_get(env_id, b"int.add")
call = Expr.ListExpr([Expr.Byte(1), Expr.Byte(2), bound])
res  = node.high_eval(env_id, call)

# sk returns a list of bytes; for 1+2 expect a single byte with value 3
print([b.value for b in res.elements])  # [3]
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
source venv/bin/activate
python3 -m unittest discover -s tests
```
