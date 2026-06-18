# lib

Python library to interact with the Astreum blockchain and its virtual machine.

[View on PyPI](https://pypi.org/project/astreum/)

## Configuration

When initializing an `astreum.Node`, pass a dictionary with any of the options below. Only the parameters you want to override need to be present – everything else falls back to its default.

### Core Configuration

| Parameter                        | Type       | Default        | Description                                                                                                                                                                            |
| -------------------------------- | ---------- | -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `chain`                          | string     | `"test"`       | Chain name (`"main"` or `"test"`). If `chain_id` is omitted, `main` maps to `1`; all other values default to test (`0`).                                                           |
| `chain_id`                       | int        | `0`            | Chain identifier used for validation (0 = test, 1 = main). If `chain` is omitted, `chain` is derived from this value (`1` => `main`, otherwise `test`).                             |
| `hot_storage_limit`              | int        | `1073741824`   | Maximum bytes kept in the hot cache before new atoms are skipped (1 GiB).                                                                                                            |
| `cold_storage_limit`             | int        | `10737418240`  | Cold storage write threshold (10 GiB by default); set to `0` to skip the limit.                                                                                                      |
| `cold_storage_path`              | string     | `None`         | Directory where persisted atoms live; Astreum creates it on startup and skips cold storage when unset.                                                                               |
| `cold_storage_scale`             | string     | `"MB"`         | Base unit for cold storage roll-up thresholds (`KB`, `MB`, or `GB`). This sets the derived `cold_storage_base_size` used for `level_0` collation and higher-level merges.           |
| `atom_fetch_interval`            | float      | `0.25`         | Poll interval (seconds) while waiting for missing atoms in `get_atom_list_from_storage`; `0` disables waiting.                                                                       |
| `atom_fetch_retries`             | int        | `8`            | Number of poll attempts for missing atoms; max wait is roughly `interval * retries`, `0` disables waiting.                                                                           |
| `verify_blockchain_interval`     | float      | `10.0`         | Delay (seconds) between consensus verification worker iterations. Defaults to `peer_timeout_interval` when not explicitly set.                                                        |
| `verification_max_stale_seconds` | int        | `10`           | Ignore otherwise-valid candidate heads whose block timestamp is older than this many seconds when selecting the latest verified chain head.                                           |
| `verification_max_future_skew`   | int        | `2`            | Ignore candidate heads whose block timestamp is more than this many seconds in the future when selecting the latest verified chain head.                                              |
| `latest_block_hash`              | hex string | `None`         | Optional 32-byte block-hash override used to preload the node's starting `latest_block_hash` from config.                                                                            |
| `verified_up_to`                 | hex string | `None`         | Optional 32-byte hash override used to preload the verification anchor (`node.verified_up_to`) from config.                                                                          |
| `logging_enabled`               | bool       | `True`         | When **False**, disable logger setup entirely, including file creation and the background logging listener thread.                                                                   |
| `logging_retention_days`         | int        | `7`            | Number of days to keep rotated log files (daily gzip).                                                                                                                                |
| `verbose`                        | bool       | `False`        | When **True**, also mirror JSON logs to stdout with a human-readable format.                                                                                                         |

### Communication

| Parameter                     | Type        | Default                       | Description                                                                                                                                          |
| ----------------------------- | ----------- | ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| `relay_secret_key`            | hex string  | Auto-generated                | X25519 private key used for the relay route; a new keypair is created when this field is omitted.                                                   |
| `relay_payment_secret_key`    | hex string  | `None`                        | Optional Ed25519 private key used for relay/storage payment channels; when set, the node can advertise a relay payment public key for paid objects. |
| `validation_secret_key`       | hex string  | `None`                        | Optional Ed25519 key that lets the node join the validation route; leave blank to opt out of validation.                                            |
| `use_ipv6`                    | bool        | `False`                       | Bind the incoming/outgoing sockets on IPv6 (the OS still listens on IPv4 if a peer speaks both).                                                   |
| `incoming_port`               | int         | `52780`                       | UDP port the relay binds to; pass `0` or omit to let the OS pick an ephemeral port.                                                                 |
| `default_seed`                | string      | `"bootstrap.astreum.org:52780"` | Default address to ping before joining; set to `None` to disable the built-in default.                                                            |
| `additional_seeds`            | list\[str\] | `[]`                          | Extra addresses appended to the bootstrap list; each must look like `host:port` or `[ipv6]:port`.                                                   |
| `peer_timeout`                | int         | `900`                         | Evict peers that have not been seen within this many seconds (15 minutes).                                                                          |
| `peer_timeout_interval`       | int         | `10`                          | How often (seconds) the peer manager checks for stale peers.                                                                                        |
| `bootstrap_retry_interval`    | int         | `30`                          | How often (seconds) to retry bootstrapping when the peer list is empty.                                                                             |
| `storage_index_interval`      | int         | `600`                         | How often (seconds) to re-advertise entries in `node.atom_advertisments` to the closest known peer.                                                |
| `storage_request_minimum_price` | int       | `1`                           | Floor price for storage/object requests; the dynamic storage request price never drops below this value.                                            |
| `storage_request_price_interval` | float    | `5.0`                         | How often (seconds) the storage thread recomputes request pricing from inbound queue pressure.                                                      |
| `fair_use_limit`              | int         | `1048576`                     | Bytes a peer may receive via shared object uploads before fair-use ratio enforcement begins (1 MiB by default).                                     |
| `fair_use_ratio`              | float       | `0.5`                         | Minimum `download/upload` ratio a peer must maintain after `fair_use_limit` is exceeded; set `0` to disable the fair-use gate.                     |
| `incoming_queue_size_limit`   | int         | `67108864`                    | Soft cap (bytes) for inbound queue usage tracked by `enqueue_incoming`; set to `0` to disable.                                                      |
| `incoming_queue_timeout`      | float       | `1.0`                         | When > 0, `enqueue_incoming` waits up to this many seconds for space before dropping the payload.                                                   |

Advertisements: `node.atom_advertisments` holds `(atom_id, payload_type, expires_at)` tuples. Use `node.add_atom_advertisement` or `node.add_atom_advertisements` to enqueue entries (`expires_at=None` keeps them indefinite). Validators automatically advertise block, transaction (main and detail lists), receipt, and account trie lists for 15 minutes by default.

> **Note**
> The peer‑to‑peer *route* used for object discovery is always enabled.
> If `validation_secret_key` is provided the node automatically joins the validation route too.

### Usage

```python
from astreum.node import Node

config = {
    "relay_secret_key": "ab…cd",             # optional – hex encoded
    "validation_secret_key": "12…34",        # optional – validator
    "hot_storage_limit": 1073741824,         # cap hot cache at 1 GiB
    "cold_storage_limit": 10737418240,       # cap cold storage at 10 GiB
    "cold_storage_path": "./data/node1",
    "incoming_port": 52780,
    "use_ipv6": False,
    "default_seed": None,
    "additional_seeds": [
        "127.0.0.1:7374"
    ]
}

node = Node(config)
# … your code …
```

## Validation Overview

Call `node.verify()` to connect the node, initialize fork tracking, and start the background consensus verification worker. The worker watches peer-reported block heads, verifies candidate forks, merges fully verified forks, and updates `node.latest_block_hash` / `node.latest_block` when a better verified head is available.

```python
node.verify()
```

`node.verify()` is idempotent while the verification thread is already running.

To start creating blocks, call `node.validate(validation_secret_key)`. Validation connects the node, prepares validator state, creates a genesis block when no latest block is configured, and starts the consensus validation worker.

```python
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

validation_secret_key = Ed25519PrivateKey.generate()

node.validate(validation_secret_key)
```

The validation worker only creates blocks when this node is the scheduled validator for the current head. It applies queued transactions when available, can create empty blocks when the queue is empty, stores the new block atoms locally, advertises them to peers, and updates `node.latest_block_hash` / `node.latest_block`.

## Transaction Overview

Use `send_transaction(...)` to atomize, store, advertise, and forward an already-signed transaction to available validators.

```python
from astreum.consensus.transaction import (
    create_transaction,
    send_transaction,
)

tx = create_transaction(
    chain_id=node.config["chain_id"],
    amount=100,
    counter=sender_account.counter + 1,
    recipient=recipient_public_key,
    sender=sender_public_key,
)
tx.sign(sender_key)
tx_hash = send_transaction(node, tx)
print(tx_hash.hex())
```

The node must already be connected and have a `latest_block`; otherwise the function raises `RuntimeError`. It writes the transaction's atoms to local storage, advertises them on the P2P network, and sends the transaction hash to peers on the validation route.


## Query API

Query functions let you fetch blocks and search transactions by height or attribute from the chain tip.

```python
from astreum import get_block, find_transactions
```

### `get_block(node, *, height)`

Fetch a single block by its chain height. Returns the `Block` object or `None` if the block hasn't been mined yet or isn't reachable.

| Parameter | Type | Description |
|-----------|------|-------------|
| `node` | `Node` | An initialised, connected Astreum node. |
| `height` | `int` | The target block height. Must be ≤ the node's latest block. |

```python
block = get_block(node, height=100_000)
if block:
    print(f"block hash: {block.expr_id.hex()[:16]}...")
    print(f"tx count:   {len(block.transactions) if block.transactions else 0}")
```

Internally walks the `previous_block` chain to the target era, then binary-descents the bloom tree by offset — approximately 11 storage fetches (O(log N)) plus the chain walk.

### `find_transactions(node, *, sender, receiver, …)`

Search for transactions matching the given filters. All filter parameters are optional — leave a filter at its default (32 zero bytes) to match anything.

When multiple filters are set, only transactions matching **all** of them are returned (AND semantics).

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node` | `Node` | — | An initialised, connected Astreum node. |
| `tx_hash` | `bytes` | `ZERO32` | Match a specific transaction hash. |
| `sender` | `bytes` | `ZERO32` | Filter by sender public key. |
| `receiver` | `bytes` | `ZERO32` | Filter by recipient public key. |
| `key` | `bytes` | `ZERO32` | Filter by contract bloom key (from `bloom.put`). |
| `start_height` | `int` | `node.latest_block.height` | Search backward from this height. |
| `end_height` | `int` | `0` | Stop when blocks drop below this height. |
| `limit` | `int` | `1` | Max results; pass `0` for no limit. |

```python
# Find up to 10 transactions from a specific sender
txs = find_transactions(node, sender=addr, limit=10)

# Find transactions in a specific height range
txs = find_transactions(
    node,
    receiver=addr,
    start_height=50_000,
    end_height=40_000,
    limit=5,
)
```

Each returned `Transaction` has its `block_hash` field set to the expr hash of the block that included it, so you can locate the containing block.

Internally uses the bloom tree index to skip eras that can't contain a match, then walks individual blocks inside candidate eras.


## Language Syntax

Astreum Language is a homoiconic, stack-based concatenative language with runtime reflection and actor support. It has a functional programming style, but also supports state and effects; `deterministic` mode disables runtime effects and loading, making it suitable for on-chain evaluation.

Astreum uses S-expressions with prefix notation. Expressions are either atoms or parenthesised lists. Lists are right-linked `Link` chains — `(a b c)` parses as `Link(a, Link(b, c))`.

### Tokens

| Token | Meaning |
|-------|---------|
| `(` `)` | Delimit a list expression. |
| `'` | Quote token — when alone, parses as the symbol `'`. Inside a list it's a regular symbol. |
| `123` `-5` | Integer literals. Parsed to `Expr.Int`. |
| `3.14` `-2.5` | Float literals. Parsed to `Expr.Float`. |
| `"hello world"` | String literals. Everything between double quotes is one token (spaces, parens preserved). Parsed to `Expr.String`. |
| `0x1f` `0Xab` | Hex bytes. Raw hex digits, no two's complement. Parsed to `Expr.Bytes`. |
| `add` `def` | Everything else is a symbol. Parsed to `Expr.Symbol`. |
| `;` | Line comment — skips to end of line. |
| `#;` | Expression skip — skips the next complete expression (including nested lists). |

### Expression types

| Type | Class | Description |
|------|-------|-------------|
| Symbol | `Expr.Symbol(value: str)` | A named identifier. |
| Bytes | `Expr.Bytes(value: bytes)` | Raw byte data. |
| Int | `Expr.Int(value: int)` | Arbitrary-precision signed integer. |
| Float | `Expr.Float(value: float)` | IEEE 754 double-precision float. |
| String | `Expr.String(value: str)` | UTF-8 string content. |
| Link | `Expr.Link(head, tail)` | A pair — the building block for lists. `Link(None, None)` is NIL. |

Links form right-associated chains. `(1 2 3)` becomes:

```
Link(Int(1), Link(Int(2), Int(3)))
```

### Environment

`Env(data={}, parent=None)` is a string-keyed binding store with parent-chain lookup. `env.get(key)` walks up parent environments. `env.put(key, value)` writes to the local environment only.

## Machine Overview

The machine evaluates an expression tree against an environment, producing a result stack.

```python
from astreum.machine.main import Machine
from astreum.machine import Env, Expr, tokenize, parse
from astreum.node import Node

node = Node()
machine = Machine(node)

# Parse source text and evaluate
tokens = tokenize("(1 2 +)")
expr, _ = parse(tokens)

env = Env()
result = machine.run(expr, env)
# result = Int(3)
```

`machine.run(expr, env)` walks the expression tree and pushes results onto a stack. Symbols that match operators pop arguments and push results. Non-operator symbols are looked up in the environment. `Bytes`, `Int`, `Float`, and `String` values are pushed as-is.

The `Machine` constructor accepts a `mode` parameter (`"dynamic"` or `"deterministic"`, default `"dynamic"`). In deterministic mode the operators `spawn`, `send`, `receive`, `eval`, `ref`, and `load` push NIL instead of executing — this ensures reproducible evaluation for contexts such as block validation.

### Metering

Every `Machine` carries a `Meter` that tracks computation cost in bytes read:

```python
machine = Machine(node, meter_enabled=True, meter_limit=1_000_000)
# MeterExceededError raised if limit is exceeded
machine.meter.used  # bytes consumed so far
```

## Operators

Operators are symbols that pop arguments from the stack and push a result.

| Operator | Stack effect | Description |
|----------|-------------|-------------|
| `+` | `a b → sum` | Addition. Int/Int → Int, Float/Float → Float, Int+Float → Float (promotion). Overflow on int→float conversion pushes NIL. |
| `-` | `a b → diff` | Subtraction. Same type rules as `+`. |
| `*` | `a b → prod` | Multiplication. Same type rules as `+`. |
| `/` | `a b → quot` | Division. Int/Int → integer division (`//`), Float/Float → float division. Int division by zero pushes NIL. |
| `%` | `a b → rem` | Modulo (Int only). Pushes NIL on non-Int. |
| `sqrt` | `a → sqrt(a)` | Square root (Float only). Pushes NIL on non-Float or negative. |
| `&` | `a b → a&b` | Bitwise AND (Bytes). |
| `\|` | `a b → a\|b` | Bitwise OR (Bytes). |
| `^` | `a b → a^b` | Bitwise XOR (Bytes). |
| `~` | `a → ~a` | Bitwise NOT (Bytes, one's complement within the operand's byte width). |
| `<<` | `value shifts → result` | Bitwise left shift (Bytes). |
| `>>>` | `value shifts → result` | Logical right shift (Bytes, zero-fill). |
| `>>` | `value shifts → result` | Arithmetic right shift (Bytes, sign-extend). |
| `rol` | `value shifts → result` | Rotate left by `shifts` bits (Bytes, within the value's bit-width). |
| `ror` | `value shifts → result` | Rotate right by `shifts` bits (Bytes, within the value's bit-width). |
| `abs` | `a → abs(a)` | Absolute value (Int or Float). Pushes NIL on non-numeric input. |
| `dip` | `v (expr) → ... v` | Temporarily remove `v`, evaluate `(expr)` on the remaining stack, then push `v` back. |
| `drop` | `a → —` | Pop and discard one value. |
| `dup` | `a → a a` | Pop and push the same value twice. |
| `swap` | `a b → b a` | Pop two values and push them back in reversed order. |
| `rot` | `a b c → b c a` | Rotate the top three stack values left. Pushes NIL if there are fewer than three values. |
| `link` | `head tail → Link(head, tail)` | Construct a `Link` pair. |
| `head` | `Link(h, t) → h` | Extract the head of a `Link`; pushes NIL on non-Link. |
| `tail` | `Link(h, t) → t` | Extract the tail of a `Link`; pushes NIL on non-Link. |
| `is_atom` | `expr → 0\|1` | Pushes `Bytes(b"\\x01")` if the value is not a `Link` (i.e. Bytes, Int, Float, String, or Symbol), else `Bytes(b"\\x00")`. |
| `is_eq` | `a b → 0\|1` | Structural equality: atoms compared by value; `Link` by recursive head+tail. Different types are never equal. |
| `eval` | `expr → result\|nil` | Pop an expression and evaluate it as code in the current environment. In deterministic mode pushes NIL. |
| `if` | `(cond) then else → result` | Evaluate `cond` quotation; if truthy (non-zero Bytes/Int/Float or non-NIL Link) evaluate `then`, otherwise evaluate `else`. |
| `fn` | `argN … arg1 params body → result` | Pops `params` (a Link chain of Symbols), `body`, and N args. Binds each arg to its param name in a child environment (parent = call-site env) and evaluates `body`. |
| `lambda` | `argN … arg1 params body → result` | Same as `fn` but with `parent=None` — the body can only access its parameters and built-in operators, not the caller's environment. |
| `def` | `name value → —` | Binds `name` (a Symbol) to `value` in the current environment. Write‑once: if the name already exists in the target environment, `def` is a no‑op (pushes NIL). |
| `'` | `(' X) → X` | Quote special form — wraps a single unevaluated expression. `(' 42)` pushes `Int(42)`. `(' (1 2 3))` pushes the entire list unevaluated as a Link chain. |
| `quote` | `a → (' a)` | Stack operator — pops a value and pushes it back wrapped in a `(' …)` quotation. |
| `symbol` | `a → symbol\|nil` | Convert Bytes (UTF-8 decoded), String, Int, or Float to `Expr.Symbol`. Pushes NIL on invalid UTF-8 bytes. |
| `str` | `a → string\|nil` | Convert any atom (Bytes/Int/Float/Symbol/String) to `Expr.String`. |
| `float` | `a → float\|nil` | Convert Int, Bytes (exactly 8 bytes, IEEE 754 little-endian), String, or Symbol to `Expr.Float`. |
| `int` | `a → int\|nil` | Convert Bytes (little-endian signed), String, Symbol, or Float to `Expr.Int`. |
| `bytes` | `a → bytes\|nil` | Convert Int (variable-length signed), Float (8-byte IEEE 754 little-endian), String, or Symbol (UTF-8) to `Expr.Bytes`. |
| `ref` | `hash → expr\|nil` | Resolve a 32‑byte hash to its stored expression via content‑addressable lookup (`node.get_expr`). For `Link` values, returns a thunk‑wrapped pair `(' head_hash ' tail_hash)` for lazy traversal of subtrees. Pushes NIL on miss, invalid hash, or deterministic mode. |
| `load` | `hash → full_expr\|nil` | Deep‑resolve a 32‑byte hash recursively through the entire sub‑tree (`node.get_expr_full`). Cost is 2× the resolved expression size. Pushes NIL on any unresolved child or deterministic mode. |

## Actor Model

The machine supports concurrent actors communicating via named mailboxes.

| Operator | Stack effect | Description |
|----------|-------------|-------------|
| `spawn` | `body name → name\|nil` | Spawn a new actor thread running `body` in a child environment. `name` must be a Symbol. Returns `name` on success, NIL if the name is already taken or threading is disabled. |
| `send` | `target msg → —` | Send `msg` to the mailbox of actor `target`. Returns nothing. Drops silently if the mailbox doesn't exist. |
| `receive` | `target → msg\|nil` | Block until a message arrives in the mailbox of actor `target`. Returns NIL if the mailbox doesn't exist. |

Actors run on daemon threads with their own environment (parented to the spawner's environment). The `Machine` constructor accepts a `mode` parameter (`"dynamic"` or `"deterministic"`, default `"dynamic"`). In deterministic mode `spawn`, `send`, `receive`, `eval`, `ref`, and `load` push NIL — they either require concurrency, runtime code-as-data, or external content lookup, all of which are disabled there for reproducible evaluation.

The `def` operator is write-once per environment: if a name already exists in the target environment's own bindings, `def` is a no-op (pushes NIL). This prevents accidental overwrites and simplifies future ZK-proof generation.

## Quickstart Example

```python
from astreum.machine.main import Machine
from astreum.machine import Env, Expr, tokenize, parse, Meter
from astreum.node import Node

node = Node()
machine = Machine(node)

# Call an fn inline: (3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn)
# Then add 2 to the result
src = "((3 5 (quote ($0 $1)) (quote ($0 $1 +)) fn) 2 +)"
tokens = tokenize(src)
expr, _ = parse(tokens)

env = Env()
stack = machine.run(expr, env)

# First value on stack is the result
result = stack[0]
print(result.value)  # 10
```

### Handling errors

`tokenize` and `parse` raise `ParseError` (from `astreum.machine.parser`) on malformed input:

```python
from astreum.machine import tokenize, parse, ParseError

try:
    tokens = tokenize("(1 2")
    expr, _ = parse(tokens)
except ParseError as e:
    print("Parse failed:", e)
```

---


## Logging

Every `Node` instance wires up structured logging automatically:

- Set `config["logging_enabled"] = False` to skip logging setup entirely. This bypasses log directory creation, file rotation, console mirroring, and the background listener thread.
- Logs land in per-instance files named `node.csv` under `%LOCALAPPDATA%\Astreum\lib-py\logs/<instance_id>` on Windows and `$XDG_STATE_HOME` (or `~/.local/state`)/`Astreum/lib-py/logs/<instance_id>` on other platforms. The `<instance_id>` is the first 16 hex characters of a BLAKE3 hash of the caller's file path, so running the node from different entry points keeps their logs isolated.
- Files rotate at midnight UTC with gzip compression (`node-YYYY-MM-DD.csv.gz`) and retain 7 days by default. Override via `config["logging_retention_days"]`.
- Each event is a single CSV row with columns `ts`, `level`, `msg`, `module`, and `func`.
- Set `config["verbose"] = True` to mirror logs to stdout in a human-friendly format like `[2025-04-13-42-59] [info] Starting Astreum Node`.
- The very first entry emitted is the banner `Starting Astreum Node`, signalling that the logging pipeline is live before other subsystems spin up.

## Testing

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

for all tests
```
python3 -m unittest discover -s tests
```

for individual tests

| Test | Method | Pass |
| --- | --- | --- |
| `pytest tests/node/test_current_validator.py` | `python3 -m unittest tests.node.test_current_validator` | ✅ |
| `pytest tests/node/test_node_connection.py` | `python3 -m unittest tests.node.test_node_connection` | ✅ |
| `pytest tests/node/test_node_init.py` | `python3 -m unittest tests.node.test_node_init` | ✅ |
| `pytest tests/node/test_node_validation.py` | `python3 -m unittest tests.node.test_node_validation` |  |
| `pytest tests/node/eval.py` | — | ✅ |
| `pytest tests/node/machine/eval.py` | `python3 -m unittest tests.node.machine.eval` | ✅ |
| `pytest tests/node/machine/parser.py` | `python3 -m unittest tests.node.machine.parser` | ✅ |
| `pytest tests/node/machine/integer.py` | `python3 -m unittest tests.node.machine.integer` | ✅ |
| `pytest tests/node/machine/stack.py` | `python3 -m unittest tests.node.machine.stack` | ✅ |
| `pytest tests/node/machine/shifts.py` | `python3 -m unittest tests.node.machine.shifts` | ✅ |
| `pytest tests/block/expr.py` | — | ✅ |
| `pytest tests/block/nonce.py` | — | ✅ |
| `pytest tests/communication/test_message_port.py` | `python3 -m unittest tests.communication.test_message_port` | ✅ |
| `pytest tests/communication/test_integration_port_handling.py` | — | ✅ |
| `pytest tests/consensus/genesis.py` | `python3 -m unittest tests.consensus.genesis` | ✅ |
| `pytest tests/consensus/test_treasury_record.py` | — | ✅ |
| `pytest tests/consensus/transaction/test_apply.py` | — | ✅ |
| `pytest tests/storage/indexing.py` | `python3 -m unittest tests.storage.indexing` | ✅ |
| `pytest tests/storage/cold.py` | `python3 -m unittest tests.storage.cold` | ✅ |
| `pytest tests/models/test_patricia.py` | `python3 -m unittest tests.models.test_patricia` | ✅ |
| `pytest tests/crypto/bloom_filter.py` | `python3 -m unittest tests.crypto.bloom_filter` | ✅ |
| `pytest tests/crypto/bloom_tree.py` | `python3 -m unittest tests.crypto.bloom_tree` | ✅ |
| `pytest tests/utils/test_logging.py` | — | ✅ |
