from typing import List

from astreum.machine.models.expression import Expr, link

from astreum.machine.evaluation.operators._def import handle_stack_def
from astreum.machine.evaluation.operators._fn import handle_stack_fn
from astreum.machine.evaluation.operators._box import handle_stack_box
from astreum.machine.evaluation.operators._if import handle_stack_if
from astreum.machine.evaluation.operators.actors.receive import handle_stack_receive
from astreum.machine.evaluation.operators.actors.send import handle_stack_send
from astreum.machine.evaluation.operators.actors.spawn import handle_stack_spawn
from astreum.machine.evaluation.operators.bytes.bitwise._and import handle_stack_and
from astreum.machine.evaluation.operators.bytes.bitwise._not import handle_stack_not
from astreum.machine.evaluation.operators.bytes.bitwise._or import handle_stack_or
from astreum.machine.evaluation.operators.bytes.bitwise.xor import handle_stack_xor
from astreum.machine.evaluation.operators.expression.head import handle_stack_head
from astreum.machine.evaluation.operators.expression.is_atom import handle_stack_is_atom
from astreum.machine.evaluation.operators.expression.is_eq import handle_stack_is_eq
from astreum.machine.evaluation.operators.expression.link import handle_stack_link
from astreum.machine.evaluation.operators.expression.tail import handle_stack_tail
from astreum.machine.evaluation.operators.expression.eval import handle_stack_eval
from astreum.machine.evaluation.operators.expression.ref import handle_stack_ref
from astreum.machine.evaluation.operators.expression.load import handle_stack_load
from astreum.machine.evaluation.operators.expression.quote import handle_stack_quote
from astreum.machine.evaluation.operators.expression.symbol import handle_stack_symbol
from astreum.machine.evaluation.operators.expression.init import handle_stack_init
from astreum.machine.evaluation.operators.expression.type import handle_stack_type
from astreum.machine.evaluation.operators.expression.id import handle_stack_id
from astreum.machine.evaluation.operators.expression.parse import handle_stack_parse
from astreum.machine.evaluation.operators.console.print import handle_stack_print
from astreum.machine.evaluation.operators.console.println import handle_stack_println
from astreum.machine.evaluation.operators.comparison import (
    handle_stack_greater_than,
    handle_stack_greater_than_or_equal,
    handle_stack_less_than,
    handle_stack_less_than_or_equal,
)
from astreum.machine.evaluation.operators.rec import handle_stack_rec
from astreum.machine.evaluation.operators.stack.dip import handle_stack_dip
from astreum.machine.evaluation.operators.stack.drop import handle_stack_drop
from astreum.machine.evaluation.operators.stack.dup import handle_stack_dup
from astreum.machine.evaluation.operators.stack.rot import handle_stack_rot
from astreum.machine.evaluation.operators.stack.swap import handle_stack_swap
from astreum.machine.evaluation.operators.arithmetic.sqrt import handle_stack_sqrt
from astreum.machine.evaluation.operators.arithmetic.abs import handle_stack_abs
from astreum.machine.evaluation.operators.arithmetic.add import handle_stack_add
from astreum.machine.evaluation.operators.arithmetic.sub import handle_stack_sub
from astreum.machine.evaluation.operators.arithmetic.mul import handle_stack_mul
from astreum.machine.evaluation.operators.arithmetic.div import handle_stack_div
from astreum.machine.evaluation.operators.arithmetic.mod import handle_stack_mod
from astreum.machine.evaluation.operators.bytes.shifts.shift import handle_stack_shift
from astreum.machine.evaluation.operators.bytes.shifts.rotate import handle_stack_rotate
from astreum.machine.evaluation.operators.string.str import handle_stack_str
from astreum.machine.evaluation.operators.float import handle_stack_float
from astreum.machine.evaluation.operators.int import handle_stack_int
from astreum.machine.evaluation.operators.bytes.main import handle_stack_bytes
from astreum.machine.evaluation.operators.bytes.concat import handle_stack_concat
from astreum.machine.evaluation.operators.bytes.split import handle_stack_split
from astreum.machine.evaluation.operators.bytes.size import handle_stack_size
from astreum.machine.evaluation.operators.bytes.index import handle_stack_index
from astreum.machine.evaluation.operators.accounts.balance import handle_stack_acc_balance
from astreum.machine.evaluation.operators.accounts.get import handle_stack_acc_get
from astreum.machine.evaluation.operators.accounts.put import handle_stack_acc_put
from astreum.machine.evaluation.operators.block.bloom_insert import handle_stack_block_bloom_insert
from astreum.machine.evaluation.operators.block.chain_id import handle_stack_block_chain_id
from astreum.machine.evaluation.operators.block.height import handle_stack_block_height
from astreum.machine.evaluation.operators.block.previous_block_hash import handle_stack_block_previous_block_hash
from astreum.machine.evaluation.operators.block.timestamp import handle_stack_block_timestamp
from astreum.machine.evaluation.operators.transaction.amount import handle_stack_tx_amount
from astreum.machine.evaluation.operators.transaction.recipient import handle_stack_tx_recipient
from astreum.machine.evaluation.operators.transaction.sender import handle_stack_tx_sender
from astreum.machine.evaluation.operators.transaction.log import handle_stack_tx_log
from astreum.machine.evaluation.operators.transaction.new import handle_stack_tx_new


OPERATOR_LIST = ["+", "-", "*", "/", "%", "&", "|", "^", "<<", "<<<", "sqrt", "abs", "~", "fn", "box", "if", "rec", "def", "link", "head", "tail", "is_atom", "is_eq", "<", ">", "<=", ">=", "drop", "dup", "swap", "rot", "dip", "spawn", "send", "receive", "eval", "ref", "load", "quote", "symbol", "str", "float", "int", "bytes", "concat", "split", "size", "index", "init", "type", "id", "parse", "print", "println", "acc.balance", "acc.get", "acc.put", "block.bloom.insert", "block.chain_id", "block.height", "block.previous_block_hash", "block.timestamp", "tx.amount", "tx.recipient", "tx.sender", "tx.new", "tx.log"]


def apply_operator(machine, symbol: Expr, stack: List[Expr], env) -> List[Expr]:
    if symbol.value == "+":
        handle_stack_add(machine, stack)

    elif symbol.value == "-":
        handle_stack_sub(machine, stack)

    elif symbol.value == "*":
        handle_stack_mul(machine, stack)

    elif symbol.value == "/":
        handle_stack_div(machine, stack)

    elif symbol.value == "%":
        handle_stack_mod(machine, stack)

    elif symbol.value == "&":
        handle_stack_and(machine, stack)

    elif symbol.value == "|":
        handle_stack_or(machine, stack)

    elif symbol.value == "^":
        handle_stack_xor(machine, stack)

    elif symbol.value == "<<":
        handle_stack_shift(machine, stack)

    elif symbol.value == "<<<":
        handle_stack_rotate(machine, stack)

    elif symbol.value == "sqrt":
        handle_stack_sqrt(machine, stack)

    elif symbol.value == "abs":
        handle_stack_abs(machine, stack)

    elif symbol.value == "~":
        handle_stack_not(machine, stack)

    elif symbol.value == "fn":
        handle_stack_fn(machine, stack, env)

    elif symbol.value == "box":
        handle_stack_box(machine, stack, env)

    elif symbol.value == "if":
        return handle_stack_if(machine, stack, env)

    elif symbol.value == "rec":
        return handle_stack_rec(machine, stack, env)

    elif symbol.value == "def":
        handle_stack_def(machine, stack, env)

    elif symbol.value == "link":
        handle_stack_link(machine, stack)

    elif symbol.value == "head":
        handle_stack_head(machine, stack)

    elif symbol.value == "tail":
        handle_stack_tail(machine, stack)

    elif symbol.value == "eval":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_eval(machine, stack, env)

    elif symbol.value == "ref":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        handle_stack_ref(machine, stack)

    elif symbol.value == "load":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        handle_stack_load(machine, stack)

    elif symbol.value == "is_atom":
        handle_stack_is_atom(machine, stack)

    elif symbol.value == "is_eq":
        handle_stack_is_eq(machine, stack)

    elif symbol.value == "<":
        handle_stack_less_than(machine, stack)

    elif symbol.value == ">":
        handle_stack_greater_than(machine, stack)

    elif symbol.value == "<=":
        handle_stack_less_than_or_equal(machine, stack)

    elif symbol.value == ">=":
        handle_stack_greater_than_or_equal(machine, stack)

    elif symbol.value == "drop":
        handle_stack_drop(machine, stack)

    elif symbol.value == "dup":
        handle_stack_dup(machine, stack)

    elif symbol.value == "swap":
        handle_stack_swap(machine, stack)

    elif symbol.value == "rot":
        handle_stack_rot(machine, stack)

    elif symbol.value == "dip":
        return handle_stack_dip(machine, stack, env)

    elif symbol.value == "spawn":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_spawn(machine, stack, env)

    elif symbol.value == "send":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_send(machine, stack)

    elif symbol.value == "receive":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_receive(machine, stack)

    elif symbol.value == "quote":
        handle_stack_quote(machine, stack)

    elif symbol.value == "symbol":
        handle_stack_symbol(machine, stack)

    elif symbol.value == "str":
        handle_stack_str(machine, stack)

    elif symbol.value == "float":
        handle_stack_float(machine, stack)

    elif symbol.value == "int":
        handle_stack_int(machine, stack)

    elif symbol.value == "bytes":
        handle_stack_bytes(machine, stack)

    elif symbol.value == "init":
        handle_stack_init(machine, stack)

    elif symbol.value == "type":
        handle_stack_type(machine, stack)

    elif symbol.value == "id":
        handle_stack_id(machine, stack)

    elif symbol.value == "parse":
        handle_stack_parse(machine, stack)

    elif symbol.value == "print":
        handle_stack_print(machine, stack)

    elif symbol.value == "println":
        handle_stack_println(machine, stack)

    elif symbol.value == "concat":
        handle_stack_concat(machine, stack)

    elif symbol.value == "split":
        handle_stack_split(machine, stack)

    elif symbol.value == "size":
        handle_stack_size(machine, stack)

    elif symbol.value == "index":
        handle_stack_index(machine, stack)

    elif symbol.value == "acc.balance":
        handle_stack_acc_balance(machine, stack)

    elif symbol.value == "acc.get":
        handle_stack_acc_get(machine, stack)

    elif symbol.value == "acc.put":
        handle_stack_acc_put(machine, stack)

    elif symbol.value == "block.chain_id":
        handle_stack_block_chain_id(machine, stack)

    elif symbol.value == "block.height":
        handle_stack_block_height(machine, stack)

    elif symbol.value == "block.previous_block_hash":
        handle_stack_block_previous_block_hash(machine, stack)

    elif symbol.value == "block.timestamp":
        handle_stack_block_timestamp(machine, stack)

    elif symbol.value == "block.bloom.insert":
        handle_stack_block_bloom_insert(machine, stack)

    elif symbol.value == "tx.amount":
        handle_stack_tx_amount(machine, stack)

    elif symbol.value == "tx.recipient":
        handle_stack_tx_recipient(machine, stack)

    elif symbol.value == "tx.sender":
        handle_stack_tx_sender(machine, stack)

    elif symbol.value == "tx.new":
        handle_stack_tx_new(machine, stack)

    elif symbol.value == "tx.log":
        handle_stack_tx_log(machine, stack)

    return stack
