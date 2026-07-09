from blake3 import blake3

from astreum.expression import Expr, NIL, link, str_, symbol
from astreum.machine import OpError
from astreum.crypto.bloom_search.variants import make_search_variants


def handle_stack_block_bloom_insert(machine, stack, env):
    if machine.tx is None:
        raise OpError("transaction context not available")
    if not stack:
        raise OpError("stack underflow")

    key = stack.pop().hash()

    if key in machine.block.pending_bloom_keys:
        return

    variants = make_search_variants(
        machine.tx.hash, machine.tx.sender, machine.tx.recipient, key
    )
    inserts = {blake3(v).digest() for v in variants}

    if machine.tx.pending_bloom_inserts & inserts:
        return

    machine.tx.pending_bloom_keys.add(key)
    machine.tx.pending_bloom_inserts |= inserts
    machine.meter.charge(8, kind="storage")


def handle_stack_block_bloom_insert_with_result(machine, stack, env):
    try:
        handle_stack_block_bloom_insert(machine, stack, env)
        stack.append(link(NIL, symbol("ok")))
    except OpError as e:
        stack.append(link(str_(str(e)), symbol("err")))
    except IndexError:
        stack.append(link(str_("stack underflow"), symbol("err")))
