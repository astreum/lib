from typing import List

from astreum.machine.models.expression import Expr, link, NIL

from astreum.machine.evaluation.operators._def import handle_stack_def
from astreum.machine.evaluation.operators._fn import handle_stack_fn
from astreum.machine.evaluation.operators._box import handle_stack_box
from astreum.machine.evaluation.operators._if import handle_stack_if
from astreum.machine.evaluation.operators._lambda import handle_stack_lambda, handle_stack_lambda_with_result
from astreum.machine.evaluation.operators.apply import handle_stack_apply
from astreum.machine.evaluation.operators.actors.receive import handle_stack_receive
from astreum.machine.evaluation.operators.actors.send import handle_stack_send
from astreum.machine.evaluation.operators.actors.spawn import handle_stack_spawn
from astreum.machine.evaluation.operators.bytes.bitwise._and import handle_stack_and
from astreum.machine.evaluation.operators.bytes.bitwise._not import handle_stack_not
from astreum.machine.evaluation.operators.bytes.bitwise._or import handle_stack_or
from astreum.machine.evaluation.operators.bytes.bitwise.xor import handle_stack_xor
from astreum.machine.evaluation.operators.expression.head import handle_stack_head
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
from astreum.machine.evaluation.operators.floats.e4m3 import handle_stack_e4m3
from astreum.machine.evaluation.operators.floats.e5m2 import handle_stack_e5m2
from astreum.machine.evaluation.operators.floats.fp16 import handle_stack_fp16
from astreum.machine.evaluation.operators.floats.bf16 import handle_stack_bf16
from astreum.machine.evaluation.operators.floats.fp32 import handle_stack_fp32
from astreum.machine.evaluation.operators.floats.fp64 import handle_stack_fp64
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
from astreum.machine.evaluation.operators.tag.ok import handle_stack_ok
from astreum.machine.evaluation.operators.tag.result import handle_stack_result
from astreum.machine.evaluation.operators._def import handle_stack_def_with_result
from astreum.machine.evaluation.operators._fn import handle_stack_fn_with_result
from astreum.machine.evaluation.operators._box import handle_stack_box_with_result
from astreum.machine.evaluation.operators._if import handle_stack_if_with_result
from astreum.machine.evaluation.operators.apply import handle_stack_apply_with_result
from astreum.machine.evaluation.operators.rec import handle_stack_rec_with_result
from astreum.machine.evaluation.operators.stack.dip import handle_stack_dip_with_result
from astreum.machine.evaluation.operators.stack.drop import handle_stack_drop_with_result
from astreum.machine.evaluation.operators.stack.dup import handle_stack_dup_with_result
from astreum.machine.evaluation.operators.stack.swap import handle_stack_swap_with_result
from astreum.machine.evaluation.operators.stack.rot import handle_stack_rot_with_result
from astreum.machine.evaluation.operators.expression.eval import handle_stack_eval_with_result
from astreum.machine.evaluation.operators.expression.head import handle_stack_head_with_result
from astreum.machine.evaluation.operators.expression.tail import handle_stack_tail_with_result
from astreum.machine.evaluation.operators.expression.link import handle_stack_link_with_result
from astreum.machine.evaluation.operators.expression.is_eq import handle_stack_is_eq_with_result
from astreum.machine.evaluation.operators.expression.quote import handle_stack_quote_with_result
from astreum.machine.evaluation.operators.expression.symbol import handle_stack_symbol_with_result
from astreum.machine.evaluation.operators.expression.ref import handle_stack_ref_with_result
from astreum.machine.evaluation.operators.expression.load import handle_stack_load_with_result
from astreum.machine.evaluation.operators.expression.init import handle_stack_init_with_result
from astreum.machine.evaluation.operators.expression.type import handle_stack_type_with_result
from astreum.machine.evaluation.operators.expression.id import handle_stack_id_with_result
from astreum.machine.evaluation.operators.expression.parse import handle_stack_parse_with_result
from astreum.machine.evaluation.operators.arithmetic.add import handle_stack_add_with_result
from astreum.machine.evaluation.operators.arithmetic.sub import handle_stack_sub_with_result
from astreum.machine.evaluation.operators.arithmetic.mul import handle_stack_mul_with_result
from astreum.machine.evaluation.operators.arithmetic.div import handle_stack_div_with_result
from astreum.machine.evaluation.operators.arithmetic.mod import handle_stack_mod_with_result
from astreum.machine.evaluation.operators.arithmetic.abs import handle_stack_abs_with_result
from astreum.machine.evaluation.operators.arithmetic.sqrt import handle_stack_sqrt_with_result
from astreum.machine.evaluation.operators.comparison import (
    handle_stack_less_than_with_result,
    handle_stack_greater_than_with_result,
    handle_stack_less_than_or_equal_with_result,
    handle_stack_greater_than_or_equal_with_result,
)
from astreum.machine.evaluation.operators.bytes.bitwise._and import handle_stack_and_with_result
from astreum.machine.evaluation.operators.bytes.bitwise._or import handle_stack_or_with_result
from astreum.machine.evaluation.operators.bytes.bitwise._not import handle_stack_not_with_result
from astreum.machine.evaluation.operators.bytes.bitwise.xor import handle_stack_xor_with_result
from astreum.machine.evaluation.operators.bytes.shifts.shift import handle_stack_shift_with_result
from astreum.machine.evaluation.operators.bytes.shifts.rotate import handle_stack_rotate_with_result
from astreum.machine.evaluation.operators.string.str import handle_stack_str_with_result
from astreum.machine.evaluation.operators.int import handle_stack_int_with_result
from astreum.machine.evaluation.operators.bytes.main import handle_stack_bytes_with_result
from astreum.machine.evaluation.operators.bytes.concat import handle_stack_concat_with_result
from astreum.machine.evaluation.operators.bytes.split import handle_stack_split_with_result
from astreum.machine.evaluation.operators.bytes.size import handle_stack_size_with_result
from astreum.machine.evaluation.operators.bytes.index import handle_stack_index_with_result
from astreum.machine.evaluation.operators.floats.fp16 import handle_stack_fp16_with_result
from astreum.machine.evaluation.operators.floats.bf16 import handle_stack_bf16_with_result
from astreum.machine.evaluation.operators.floats.e4m3 import handle_stack_e4m3_with_result
from astreum.machine.evaluation.operators.floats.e5m2 import handle_stack_e5m2_with_result
from astreum.machine.evaluation.operators.floats.fp32 import handle_stack_fp32_with_result
from astreum.machine.evaluation.operators.floats.fp64 import handle_stack_fp64_with_result
from astreum.machine.evaluation.operators.actors.spawn import handle_stack_spawn_with_result
from astreum.machine.evaluation.operators.actors.send import handle_stack_send_with_result
from astreum.machine.evaluation.operators.actors.receive import handle_stack_receive_with_result
from astreum.machine.evaluation.operators.accounts.balance import handle_stack_acc_balance_with_result
from astreum.machine.evaluation.operators.accounts.get import handle_stack_acc_get_with_result
from astreum.machine.evaluation.operators.accounts.put import handle_stack_acc_put_with_result
from astreum.machine.evaluation.operators.block.bloom_insert import handle_stack_block_bloom_insert_with_result
from astreum.machine.evaluation.operators.block.chain_id import handle_stack_block_chain_id_with_result
from astreum.machine.evaluation.operators.block.height import handle_stack_block_height_with_result
from astreum.machine.evaluation.operators.block.previous_block_hash import handle_stack_block_previous_block_hash_with_result
from astreum.machine.evaluation.operators.block.timestamp import handle_stack_block_timestamp_with_result
from astreum.machine.evaluation.operators.transaction.amount import handle_stack_tx_amount_with_result
from astreum.machine.evaluation.operators.transaction.recipient import handle_stack_tx_recipient_with_result
from astreum.machine.evaluation.operators.transaction.sender import handle_stack_tx_sender_with_result
from astreum.machine.evaluation.operators.transaction.log import handle_stack_tx_log_with_result
from astreum.machine.evaluation.operators.transaction.new import handle_stack_tx_new_with_result
from astreum.machine.evaluation.operators.console.print import handle_stack_print_with_result
from astreum.machine.evaluation.operators.console.println import handle_stack_println_with_result
from astreum.machine.evaluation.operators.tag._match import handle_stack_match
from astreum.machine.evaluation.operators.tag.err import handle_stack_err
from astreum.machine.evaluation.operators.expression._is import handle_stack_is


OPERATOR_LIST = ["+", "-", "*", "/", "%", "&", "|", "^", "<<", "<<<", "sqrt", "abs", "~", "fn", "box", "if", "rec", "def", "link", "head", "tail", "is_eq", "<", ">", "<=", ">=", "drop", "dup", "swap", "rot", "dip", "spawn", "send", "receive", "eval", "ref", "load", "quote", "symbol", "str", "e4m3", "e5m2", "fp16", "bf16", "fp32", "fp64", "int", "bytes", "concat", "split", "size", "index", "init", "type", "id", "parse", "print", "println", "acc.balance", "acc.get", "acc.put", "block.bloom.insert", "block.chain_id", "block.height", "block.previous_block_hash", "block.timestamp", "tx.amount", "tx.recipient", "tx.sender", "tx.new", "tx.log", "lambda", "apply", "ok", "err", "result", "+?", "-?", "*?", "/?", "%?", "abs?", "sqrt?", "<?", ">?", "<=?", ">=?", "&?", "|?", "^?", "~?", "<<?", "<<<?", "link?", "head?", "tail?", "symbol?", "str?", "int?", "bytes?", "concat?", "split?", "size?", "index?", "fp16?", "bf16?", "e4m3?", "e5m2?", "fp32?", "fp64?", "dup?", "swap?", "rot?", "drop?", "is_eq?", "quote?", "type?", "parse?", "ref?", "load?", "init?", "id?", "def?", "fn?", "box?", "rec?", "if?", "dip?", "eval?", "lambda?", "apply?", "spawn?", "send?", "receive?", "block.bloom.insert?", "match", "is"]


def apply_operator(machine, symbol: Expr, stack: List[Expr], env) -> List[Expr]:
    if symbol.value == "+":
        handle_stack_add(machine, stack, env)

    elif symbol.value == "-":
        handle_stack_sub(machine, stack, env)

    elif symbol.value == "*":
        handle_stack_mul(machine, stack, env)

    elif symbol.value == "/":
        handle_stack_div(machine, stack, env)

    elif symbol.value == "%":
        handle_stack_mod(machine, stack, env)

    elif symbol.value == "&":
        handle_stack_and(machine, stack, env)

    elif symbol.value == "|":
        handle_stack_or(machine, stack, env)

    elif symbol.value == "^":
        handle_stack_xor(machine, stack, env)

    elif symbol.value == "<<":
        handle_stack_shift(machine, stack, env)

    elif symbol.value == "<<<":
        handle_stack_rotate(machine, stack, env)

    elif symbol.value == "sqrt":
        handle_stack_sqrt(machine, stack, env)

    elif symbol.value == "abs":
        handle_stack_abs(machine, stack, env)

    elif symbol.value == "~":
        handle_stack_not(machine, stack, env)

    elif symbol.value == "fn":
        handle_stack_fn(machine, stack, env)

    elif symbol.value == "box":
        handle_stack_box(machine, stack, env)

    elif symbol.value == "lambda":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return stack
        handle_stack_lambda(machine, stack, env)

    elif symbol.value == "lambda?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return stack
        handle_stack_lambda_with_result(machine, stack, env)

    elif symbol.value == "apply":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return stack
        handle_stack_apply(machine, stack, env)

    elif symbol.value == "if":
        return handle_stack_if(machine, stack, env)

    elif symbol.value == "rec":
        return handle_stack_rec(machine, stack, env)

    elif symbol.value == "def":
        handle_stack_def(machine, stack, env)

    elif symbol.value == "link":
        handle_stack_link(machine, stack, env)

    elif symbol.value == "head":
        handle_stack_head(machine, stack, env)

    elif symbol.value == "tail":
        handle_stack_tail(machine, stack, env)

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
        handle_stack_ref(machine, stack, env)

    elif symbol.value == "load":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        handle_stack_load(machine, stack, env)

    elif symbol.value == "is_eq":
        handle_stack_is_eq(machine, stack, env)

    elif symbol.value == "<":
        handle_stack_less_than(machine, stack, env)

    elif symbol.value == ">":
        handle_stack_greater_than(machine, stack, env)

    elif symbol.value == "<=":
        handle_stack_less_than_or_equal(machine, stack, env)

    elif symbol.value == ">=":
        handle_stack_greater_than_or_equal(machine, stack, env)

    elif symbol.value == "drop":
        handle_stack_drop(machine, stack, env)

    elif symbol.value == "dup":
        handle_stack_dup(machine, stack, env)

    elif symbol.value == "swap":
        handle_stack_swap(machine, stack, env)

    elif symbol.value == "rot":
        handle_stack_rot(machine, stack, env)

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
        return handle_stack_send(machine, stack, env)

    elif symbol.value == "receive":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_receive(machine, stack, env)

    elif symbol.value == "quote":
        handle_stack_quote(machine, stack, env)

    elif symbol.value == "symbol":
        handle_stack_symbol(machine, stack, env)

    elif symbol.value == "str":
        handle_stack_str(machine, stack, env)

    elif symbol.value == "e4m3":
        handle_stack_e4m3(machine, stack, env)

    elif symbol.value == "e5m2":
        handle_stack_e5m2(machine, stack, env)

    elif symbol.value == "fp16":
        handle_stack_fp16(machine, stack, env)

    elif symbol.value == "bf16":
        handle_stack_bf16(machine, stack, env)

    elif symbol.value == "fp32":
        handle_stack_fp32(machine, stack, env)

    elif symbol.value == "fp64":
        handle_stack_fp64(machine, stack, env)

    elif symbol.value == "int":
        handle_stack_int(machine, stack, env)

    elif symbol.value == "bytes":
        handle_stack_bytes(machine, stack, env)

    elif symbol.value == "init":
        handle_stack_init(machine, stack, env)

    elif symbol.value == "type":
        handle_stack_type(machine, stack, env)

    elif symbol.value == "id":
        handle_stack_id(machine, stack, env)

    elif symbol.value == "parse":
        handle_stack_parse(machine, stack, env)

    elif symbol.value == "print":
        handle_stack_print(machine, stack, env)

    elif symbol.value == "println":
        handle_stack_println(machine, stack, env)

    elif symbol.value == "concat":
        handle_stack_concat(machine, stack, env)

    elif symbol.value == "split":
        handle_stack_split(machine, stack, env)

    elif symbol.value == "size":
        handle_stack_size(machine, stack, env)

    elif symbol.value == "index":
        handle_stack_index(machine, stack, env)

    elif symbol.value == "acc.balance":
        handle_stack_acc_balance(machine, stack, env)

    elif symbol.value == "acc.get":
        handle_stack_acc_get(machine, stack, env)

    elif symbol.value == "acc.put":
        handle_stack_acc_put(machine, stack, env)

    elif symbol.value == "block.chain_id":
        handle_stack_block_chain_id(machine, stack, env)

    elif symbol.value == "block.height":
        handle_stack_block_height(machine, stack, env)

    elif symbol.value == "block.previous_block_hash":
        handle_stack_block_previous_block_hash(machine, stack, env)

    elif symbol.value == "block.timestamp":
        handle_stack_block_timestamp(machine, stack, env)

    elif symbol.value == "block.bloom.insert":
        handle_stack_block_bloom_insert(machine, stack, env)

    elif symbol.value == "tx.amount":
        handle_stack_tx_amount(machine, stack, env)

    elif symbol.value == "tx.recipient":
        handle_stack_tx_recipient(machine, stack, env)

    elif symbol.value == "tx.sender":
        handle_stack_tx_sender(machine, stack, env)

    elif symbol.value == "tx.new":
        handle_stack_tx_new(machine, stack, env)

    elif symbol.value == "tx.log":
        handle_stack_tx_log(machine, stack, env)

    elif symbol.value == "ok":
        handle_stack_ok(machine, stack, env)

    elif symbol.value == "err":
        handle_stack_err(machine, stack, env)

    elif symbol.value == "result":
        return handle_stack_result(machine, stack, env)

    elif symbol.value == "+?":
        handle_stack_add_with_result(machine, stack, env)

    elif symbol.value == "-?":
        handle_stack_sub_with_result(machine, stack, env)

    elif symbol.value == "*?":
        handle_stack_mul_with_result(machine, stack, env)

    elif symbol.value == "/?":
        handle_stack_div_with_result(machine, stack, env)

    elif symbol.value == "%?":
        handle_stack_mod_with_result(machine, stack, env)

    elif symbol.value == "abs?":
        handle_stack_abs_with_result(machine, stack, env)

    elif symbol.value == "sqrt?":
        handle_stack_sqrt_with_result(machine, stack, env)

    elif symbol.value == "<?":
        handle_stack_less_than_with_result(machine, stack, env)

    elif symbol.value == ">?":
        handle_stack_greater_than_with_result(machine, stack, env)

    elif symbol.value == "<=?":
        handle_stack_less_than_or_equal_with_result(machine, stack, env)

    elif symbol.value == ">=?":
        handle_stack_greater_than_or_equal_with_result(machine, stack, env)

    elif symbol.value == "&?":
        handle_stack_and_with_result(machine, stack, env)

    elif symbol.value == "|?":
        handle_stack_or_with_result(machine, stack, env)

    elif symbol.value == "^?":
        handle_stack_xor_with_result(machine, stack, env)

    elif symbol.value == "~?":
        handle_stack_not_with_result(machine, stack, env)

    elif symbol.value == "<<?":
        handle_stack_shift_with_result(machine, stack, env)

    elif symbol.value == "<<<?":
        handle_stack_rotate_with_result(machine, stack, env)

    elif symbol.value == "link?":
        handle_stack_link_with_result(machine, stack, env)

    elif symbol.value == "head?":
        handle_stack_head_with_result(machine, stack, env)

    elif symbol.value == "tail?":
        handle_stack_tail_with_result(machine, stack, env)

    elif symbol.value == "symbol?":
        handle_stack_symbol_with_result(machine, stack, env)

    elif symbol.value == "str?":
        handle_stack_str_with_result(machine, stack, env)

    elif symbol.value == "int?":
        handle_stack_int_with_result(machine, stack, env)

    elif symbol.value == "bytes?":
        handle_stack_bytes_with_result(machine, stack, env)

    elif symbol.value == "concat?":
        handle_stack_concat_with_result(machine, stack, env)

    elif symbol.value == "split?":
        handle_stack_split_with_result(machine, stack, env)

    elif symbol.value == "size?":
        handle_stack_size_with_result(machine, stack, env)

    elif symbol.value == "index?":
        handle_stack_index_with_result(machine, stack, env)

    elif symbol.value == "fp16?":
        handle_stack_fp16_with_result(machine, stack, env)

    elif symbol.value == "bf16?":
        handle_stack_bf16_with_result(machine, stack, env)

    elif symbol.value == "e4m3?":
        handle_stack_e4m3_with_result(machine, stack, env)

    elif symbol.value == "e5m2?":
        handle_stack_e5m2_with_result(machine, stack, env)

    elif symbol.value == "fp32?":
        handle_stack_fp32_with_result(machine, stack, env)

    elif symbol.value == "fp64?":
        handle_stack_fp64_with_result(machine, stack, env)

    elif symbol.value == "dup?":
        handle_stack_dup_with_result(machine, stack, env)

    elif symbol.value == "swap?":
        handle_stack_swap_with_result(machine, stack, env)

    elif symbol.value == "rot?":
        handle_stack_rot_with_result(machine, stack, env)

    elif symbol.value == "drop?":
        handle_stack_drop_with_result(machine, stack, env)

    elif symbol.value == "is_eq?":
        handle_stack_is_eq_with_result(machine, stack, env)

    elif symbol.value == "quote?":
        handle_stack_quote_with_result(machine, stack, env)

    elif symbol.value == "type?":
        handle_stack_type_with_result(machine, stack, env)

    elif symbol.value == "parse?":
        handle_stack_parse_with_result(machine, stack, env)

    elif symbol.value == "ref?":
        handle_stack_ref_with_result(machine, stack, env)

    elif symbol.value == "load?":
        handle_stack_load_with_result(machine, stack, env)

    elif symbol.value == "init?":
        handle_stack_init_with_result(machine, stack, env)

    elif symbol.value == "id?":
        handle_stack_id_with_result(machine, stack, env)

    elif symbol.value == "def?":
        handle_stack_def_with_result(machine, stack, env)

    elif symbol.value == "fn?":
        handle_stack_fn_with_result(machine, stack, env)

    elif symbol.value == "box?":
        handle_stack_box_with_result(machine, stack, env)

    elif symbol.value == "rec?":
        return handle_stack_rec_with_result(machine, stack, env)

    elif symbol.value == "if?":
        return handle_stack_if_with_result(machine, stack, env)

    elif symbol.value == "dip?":
        return handle_stack_dip_with_result(machine, stack, env)

    elif symbol.value == "eval?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_eval_with_result(machine, stack, env)

    elif symbol.value == "apply?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(NIL)
            return stack
        handle_stack_apply_with_result(machine, stack, env)

    elif symbol.value == "spawn?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_spawn_with_result(machine, stack, env)

    elif symbol.value == "send?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_send_with_result(machine, stack, env)

    elif symbol.value == "receive?":
        if machine.mode == "deterministic":
            machine.meter.charge_bytes(1)
            stack.append(link(None, None))
            return stack
        return handle_stack_receive_with_result(machine, stack, env)

    elif symbol.value == "block.bloom.insert?":
        handle_stack_block_bloom_insert_with_result(machine, stack, env)

    elif symbol.value == "match":
        return handle_stack_match(machine, stack, env)

    elif symbol.value == "is":
        handle_stack_is(machine, stack, env)

    return stack
