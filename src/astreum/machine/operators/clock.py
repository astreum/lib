import time

from astreum.expression import int_


def handle_stack_time(machine, stack, env):
    secs = int(time.time())
    val = int_(secs)
    machine.meter.charge_bytes(val.size())
    stack.append(val)


def handle_stack_clock(machine, stack, env):
    ns = time.perf_counter_ns()
    val = int_(ns)
    machine.meter.charge_bytes(val.size())
    stack.append(val)
