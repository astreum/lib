from queue import Queue
import threading
import uuid
from typing import Dict, Optional

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.meter import Meter, MeterExceededError
from astreum.machine.evaluation.main import evaluation

class Machine():
    def __init__(self, node: "Node", *, meter_limit: int = None, mode: str = "dynamic"):
        if mode not in ("dynamic", "deterministic"):
            raise ValueError(f"Invalid mode: {mode!r}. Must be 'dynamic' or 'deterministic'.")
        self.node = node
        self.mailboxes: Dict[str, Queue] = {}
        self.lock = threading.Lock()
        self.mode = mode
        self.meter = Meter(limit=meter_limit)
        self.nested_call_depth: int = 0
        self.tx: Optional[object] = None
        self.block: Optional[object] = None
        self.logs: list[Expr] = []
        self.log_contract_entries: list = []
        self.library: Dict[uuid.UUID, Env] = {}
    
    def snapshot_env(self, env: Env) -> uuid.UUID:
        if env is None:
            env = Env()
        parent_uuid = None
        if env.parent is not None:
            parent_uuid = self.snapshot_env(env.parent)
        snapshot = Env(data=dict(env.data), parent=self.library[parent_uuid] if parent_uuid else None)
        env_uuid = uuid.uuid4()
        self.library[env_uuid] = snapshot
        return env_uuid

    def run(self, expr: "Expr", env: "Env" = None):
        if env is None:
            env = Env()
        stack = []
        evaluation(self, expr, stack, env)
        return stack[-1] if stack else NIL

    def spawn_actor(self, body: "Expr", actor_name: str, parent_env: "Env"):
        with self.lock:
            if actor_name in self.mailboxes:
                return False
        
        q = Queue()
        with self.lock:
            self.mailboxes[actor_name] = q
        
        thread = threading.Thread(
            target=self.run_actor,
            args=(body, actor_name, parent_env),
            daemon=True
        )
        thread.start()
        return True

    def run_actor(self, body: "Expr", actor_name: str, parent_env: "Env"):
        env = Env(parent=parent_env)
        stack = []
        try:
            evaluation(self, body, stack, env)
        except MeterExceededError:
            pass
        finally:
            with self.lock:
                self.mailboxes.pop(actor_name, None)

    def enable_console(self):
        self._stdin_stop = threading.Event()
        q = Queue()
        with self.lock:
            self.mailboxes["@pipe"] = q
        t = threading.Thread(target=self._stdin_reader, daemon=True)
        t.start()

    def disable_console(self):
        self._stdin_stop.set()

    def _stdin_reader(self):
        import sys
        from astreum.machine.models.expression import str_
        while not self._stdin_stop.is_set():
            try:
                line = sys.stdin.readline()
            except EOFError:
                break
            if not line:
                self._stdin_stop.set()
                break
            line = line.rstrip("\n")
            mbox = self.mailboxes.get("@pipe")
            if mbox is not None:
                mbox.put(str_(line))
