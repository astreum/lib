from queue import Queue
import threading
from typing import Dict, Optional

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr, NIL
from astreum.machine.models.meter import Meter, MeterExceededError
from astreum.machine.evaluation.main import evaluation

class Machine():
    def __init__(self, node: "Node", *, meter_enabled: bool = True, meter_limit: int = None, mode: str = "dynamic"):
        if mode not in ("dynamic", "deterministic"):
            raise ValueError(f"Invalid mode: {mode!r}. Must be 'dynamic' or 'deterministic'.")
        self.node = node
        self.mailboxes: Dict[str, Queue] = {}
        self.lock = threading.Lock()
        self.mode = mode
        self.meter = Meter(enabled=meter_enabled, limit=meter_limit)
        self.global_env = Env()
        self.accounts: Dict[bytes, object] = {}
        self.tx: Optional[object] = None
        self.block: Optional[object] = None
    
    def run(self, expr: "Expr", env: "Env" = None):
        if env is None:
            env = self.global_env
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
        env = Env(parent=parent_env, def_target=self.global_env)
        stack = []
        try:
            evaluation(self, body, stack, env)
        except MeterExceededError:
            pass
        finally:
            with self.lock:
                self.mailboxes.pop(actor_name, None)
