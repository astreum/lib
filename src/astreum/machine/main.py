from queue import Queue
import threading
from typing import Dict

from astreum.machine.models.environment import Env
from astreum.machine.models.expression import Expr
from astreum.machine.models.meter import Meter, MeterExceededError
from astreum.machine.evaluation.main import evaluation

class Machine():
    def __init__(self, node: "Node", *, meter_enabled: bool = True, meter_limit: int = None, allow_threading: bool = True):
        self.node = node
        self.mailboxes: Dict[str, Queue] = {}
        self.lock = threading.Lock()
        self.allow_threading = allow_threading
        self.meter = Meter(enabled=meter_enabled, limit=meter_limit)
    
    def run(self, expr: "Expr", env: "Env" = Env()):
        stack = []
        evaluation(self, expr, stack, env)
        return stack

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
