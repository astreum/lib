from typing import List

from astreum.expression import Expr, link, NIL

from astreum.machine.operators._def import handle_stack_def
from astreum.machine.operators._if import handle_stack_if
from astreum.machine.operators._closure import handle_stack_closure, handle_stack_closure_with_result
from astreum.machine.operators.apply import handle_stack_apply
from astreum.machine.operators.actors.receive import handle_stack_receive
from astreum.machine.operators.actors.send import handle_stack_send
from astreum.machine.operators.actors.spawn import handle_stack_spawn
from astreum.machine.operators.bytes.bitwise._and import handle_stack_and
from astreum.machine.operators.bytes.bitwise._not import handle_stack_not
from astreum.machine.operators.bytes.bitwise._or import handle_stack_or
from astreum.machine.operators.bytes.bitwise.xor import handle_stack_xor
from astreum.machine.operators.expression.head import handle_stack_head
from astreum.machine.operators.expression.is_eq import handle_stack_is_eq
from astreum.machine.operators.expression.link import handle_stack_link
from astreum.machine.operators.expression.tail import handle_stack_tail
from astreum.machine.operators.expression.eval import handle_stack_eval
from astreum.machine.operators.expression.ref import handle_stack_ref
from astreum.machine.operators.expression.load import handle_stack_load
from astreum.machine.operators.expression.quote import handle_stack_quote
from astreum.machine.operators.expression.symbol import handle_stack_symbol
from astreum.machine.operators.expression.init import handle_stack_init
from astreum.machine.operators.expression.type import handle_stack_type
from astreum.machine.operators.expression.id import handle_stack_id
from astreum.machine.operators.expression.parse import handle_stack_parse
from astreum.machine.operators.clock import handle_stack_clock, handle_stack_time
from astreum.machine.operators.console.print import handle_stack_print
from astreum.machine.operators.console.println import handle_stack_println
from astreum.machine.operators.comparison import (
    handle_stack_greater_than,
    handle_stack_greater_than_or_equal,
    handle_stack_less_than,
    handle_stack_less_than_or_equal,
)
from astreum.machine.operators.rec import handle_stack_rec
from astreum.machine.operators.stack.dip import handle_stack_dip
from astreum.machine.operators.stack.drop import handle_stack_drop
from astreum.machine.operators.stack.dup import handle_stack_dup
from astreum.machine.operators.stack.rot import handle_stack_rot
from astreum.machine.operators.stack.swap import handle_stack_swap
from astreum.machine.operators.arithmetic.sqrt import handle_stack_sqrt
from astreum.machine.operators.arithmetic.abs import handle_stack_abs
from astreum.machine.operators.arithmetic.add import handle_stack_add
from astreum.machine.operators.arithmetic.sub import handle_stack_sub
from astreum.machine.operators.arithmetic.mul import handle_stack_mul
from astreum.machine.operators.arithmetic.div import handle_stack_div
from astreum.machine.operators.arithmetic.mod import handle_stack_mod
from astreum.machine.operators.bytes.shifts.shift import handle_stack_shift
from astreum.machine.operators.bytes.shifts.rotate import handle_stack_rotate
from astreum.machine.operators.string.str import handle_stack_str
from astreum.machine.operators.floats.e4m3 import handle_stack_e4m3
from astreum.machine.operators.floats.e5m2 import handle_stack_e5m2
from astreum.machine.operators.floats.fp16 import handle_stack_fp16
from astreum.machine.operators.floats.bf16 import handle_stack_bf16
from astreum.machine.operators.floats.fp32 import handle_stack_fp32
from astreum.machine.operators.floats.fp64 import handle_stack_fp64
from astreum.machine.operators.int import handle_stack_int
from astreum.machine.operators.bytes.main import handle_stack_bytes
from astreum.machine.operators.sequence.map import handle_stack_map
from astreum.machine.operators.sequence.filter import handle_stack_filter
from astreum.machine.operators.sequence.each import handle_stack_each
from astreum.machine.operators.sequence.fold import handle_stack_fold
from astreum.machine.operators.sequence.zip import handle_stack_zip
from astreum.machine.operators.sequence.find import handle_stack_find
from astreum.machine.operators.sequence.count import handle_stack_count
from astreum.machine.operators.sequence.reverse import handle_stack_reverse
from astreum.machine.operators.sequence.concat import handle_stack_concat
from astreum.machine.operators.sequence.split import handle_stack_split
from astreum.machine.operators.sequence.index import handle_stack_index
from astreum.machine.operators.accounts.balance import handle_stack_acc_balance
from astreum.machine.operators.accounts.get import handle_stack_acc_get
from astreum.machine.operators.accounts.put import handle_stack_acc_put
from astreum.machine.operators.block.bloom_insert import handle_stack_block_bloom_insert
from astreum.machine.operators.block.chain_id import handle_stack_block_chain_id
from astreum.machine.operators.block.height import handle_stack_block_height
from astreum.machine.operators.block.previous_block_hash import handle_stack_block_previous_block_hash
from astreum.machine.operators.block.timestamp import handle_stack_block_timestamp
from astreum.machine.operators.transaction.amount import handle_stack_tx_amount
from astreum.machine.operators.transaction.recipient import handle_stack_tx_recipient
from astreum.machine.operators.transaction.sender import handle_stack_tx_sender
from astreum.machine.operators.transaction.log import handle_stack_tx_log
from astreum.machine.operators.transaction.new import handle_stack_tx_new
from astreum.machine.operators.tag.ok import handle_stack_ok
from astreum.machine.operators.tag.result import handle_stack_result
from astreum.machine.operators._def import handle_stack_def_with_result
from astreum.machine.operators._if import handle_stack_if_with_result
from astreum.machine.operators.apply import handle_stack_apply_with_result
from astreum.machine.operators.rec import handle_stack_rec_with_result
from astreum.machine.operators.stack.dip import handle_stack_dip_with_result
from astreum.machine.operators.stack.drop import handle_stack_drop_with_result
from astreum.machine.operators.stack.dup import handle_stack_dup_with_result
from astreum.machine.operators.stack.swap import handle_stack_swap_with_result
from astreum.machine.operators.stack.rot import handle_stack_rot_with_result
from astreum.machine.operators.expression.eval import handle_stack_eval_with_result
from astreum.machine.operators.expression.head import handle_stack_head_with_result
from astreum.machine.operators.expression.tail import handle_stack_tail_with_result
from astreum.machine.operators.expression.link import handle_stack_link_with_result
from astreum.machine.operators.expression.is_eq import handle_stack_is_eq_with_result
from astreum.machine.operators.expression.quote import handle_stack_quote_with_result
from astreum.machine.operators.expression.symbol import handle_stack_symbol_with_result
from astreum.machine.operators.expression.ref import handle_stack_ref_with_result
from astreum.machine.operators.expression.load import handle_stack_load_with_result
from astreum.machine.operators.expression.init import handle_stack_init_with_result
from astreum.machine.operators.expression.type import handle_stack_type_with_result
from astreum.machine.operators.expression.id import handle_stack_id_with_result
from astreum.machine.operators.expression.parse import handle_stack_parse_with_result
from astreum.machine.operators.arithmetic.add import handle_stack_add_with_result
from astreum.machine.operators.arithmetic.sub import handle_stack_sub_with_result
from astreum.machine.operators.arithmetic.mul import handle_stack_mul_with_result
from astreum.machine.operators.arithmetic.div import handle_stack_div_with_result
from astreum.machine.operators.arithmetic.mod import handle_stack_mod_with_result
from astreum.machine.operators.arithmetic.abs import handle_stack_abs_with_result
from astreum.machine.operators.arithmetic.sqrt import handle_stack_sqrt_with_result
from astreum.machine.operators.comparison import (
    handle_stack_less_than_with_result,
    handle_stack_greater_than_with_result,
    handle_stack_less_than_or_equal_with_result,
    handle_stack_greater_than_or_equal_with_result,
)
from astreum.machine.operators.bytes.bitwise._and import handle_stack_and_with_result
from astreum.machine.operators.bytes.bitwise._or import handle_stack_or_with_result
from astreum.machine.operators.bytes.bitwise._not import handle_stack_not_with_result
from astreum.machine.operators.bytes.bitwise.xor import handle_stack_xor_with_result
from astreum.machine.operators.bytes.shifts.shift import handle_stack_shift_with_result
from astreum.machine.operators.bytes.shifts.rotate import handle_stack_rotate_with_result
from astreum.machine.operators.string.str import handle_stack_str_with_result
from astreum.machine.operators.int import handle_stack_int_with_result
from astreum.machine.operators.bytes.main import handle_stack_bytes_with_result
from astreum.machine.operators.sequence.map import handle_stack_map_with_result
from astreum.machine.operators.sequence.filter import handle_stack_filter_with_result
from astreum.machine.operators.sequence.each import handle_stack_each_with_result
from astreum.machine.operators.sequence.fold import handle_stack_fold_with_result
from astreum.machine.operators.sequence.zip import handle_stack_zip_with_result
from astreum.machine.operators.sequence.find import handle_stack_find_with_result
from astreum.machine.operators.sequence.count import handle_stack_count_with_result
from astreum.machine.operators.sequence.reverse import handle_stack_reverse_with_result
from astreum.machine.operators.sequence.concat import handle_stack_concat_with_result
from astreum.machine.operators.sequence.split import handle_stack_split_with_result
from astreum.machine.operators.sequence.index import handle_stack_index_with_result
from astreum.machine.operators.floats.fp16 import handle_stack_fp16_with_result
from astreum.machine.operators.floats.bf16 import handle_stack_bf16_with_result
from astreum.machine.operators.floats.e4m3 import handle_stack_e4m3_with_result
from astreum.machine.operators.floats.e5m2 import handle_stack_e5m2_with_result
from astreum.machine.operators.floats.fp32 import handle_stack_fp32_with_result
from astreum.machine.operators.floats.fp64 import handle_stack_fp64_with_result
from astreum.machine.operators.actors.spawn import handle_stack_spawn_with_result
from astreum.machine.operators.actors.send import handle_stack_send_with_result
from astreum.machine.operators.actors.receive import handle_stack_receive_with_result
from astreum.machine.operators.accounts.balance import handle_stack_acc_balance_with_result
from astreum.machine.operators.accounts.get import handle_stack_acc_get_with_result
from astreum.machine.operators.accounts.put import handle_stack_acc_put_with_result
from astreum.machine.operators.block.bloom_insert import handle_stack_block_bloom_insert_with_result
from astreum.machine.operators.block.chain_id import handle_stack_block_chain_id_with_result
from astreum.machine.operators.block.height import handle_stack_block_height_with_result
from astreum.machine.operators.block.previous_block_hash import handle_stack_block_previous_block_hash_with_result
from astreum.machine.operators.block.timestamp import handle_stack_block_timestamp_with_result
from astreum.machine.operators.transaction.amount import handle_stack_tx_amount_with_result
from astreum.machine.operators.transaction.recipient import handle_stack_tx_recipient_with_result
from astreum.machine.operators.transaction.sender import handle_stack_tx_sender_with_result
from astreum.machine.operators.transaction.log import handle_stack_tx_log_with_result
from astreum.machine.operators.transaction.new import handle_stack_tx_new_with_result
from astreum.machine.operators.console.print import handle_stack_print_with_result
from astreum.machine.operators.console.println import handle_stack_println_with_result
from astreum.machine.operators.tag._match import handle_stack_match
from astreum.machine.operators.tag.err import handle_stack_err
from astreum.machine.operators.expression._is import handle_stack_is


def _with_variants(*names):
    result = []
    for n in names:
        result.append(n)
        result.append(f"{n}?")
    return tuple(result)


ARITHMETIC_OPERATORS = _with_variants("+", "-", "*", "/", "%", "sqrt", "abs")
BITWISE_OPERATORS = _with_variants("&", "|", "^", "~")
SHIFT_OPERATORS = _with_variants("<<", "<<<")
COMPARISON_OPERATORS = _with_variants("<", ">", "<=", ">=")
STACK_OPERATORS = _with_variants("drop", "dup", "swap", "rot", "dip")
SEQUENCE_OPERATORS = _with_variants("concat", "split", "index", "count", "reverse", "map", "filter", "each", "fold", "zip", "find")
CONVERSION_OPERATORS = _with_variants("str", "int", "bytes", "e4m3", "e5m2", "fp16", "bf16", "fp32", "fp64")
FLOW_OPERATORS = _with_variants("def", "rec", "if", "closure", "apply")
ACTOR_OPERATORS = _with_variants("spawn", "send", "receive")
EXPRESSION_OPERATORS = _with_variants("link", "head", "tail", "is_eq", "symbol", "quote", "type", "parse", "ref", "load", "init", "id", "eval") + ("is",)
BLOCK_OPERATORS = _with_variants("block.bloom.insert") + ("block.chain_id", "block.height", "block.previous_block_hash", "block.timestamp")

TIME_OPERATORS = ("time", "clock")
CONSOLE_OPERATORS = ("print", "println")
ACCOUNT_OPERATORS = ("acc.balance", "acc.get", "acc.put")
TX_OPERATORS = ("tx.amount", "tx.recipient", "tx.sender", "tx.new", "tx.log")
TAG_OPERATORS = ("ok", "err", "result", "match")

OPERATOR_LIST = frozenset(
    ARITHMETIC_OPERATORS + BITWISE_OPERATORS + SHIFT_OPERATORS +
    COMPARISON_OPERATORS + STACK_OPERATORS + EXPRESSION_OPERATORS +
    SEQUENCE_OPERATORS + CONVERSION_OPERATORS + FLOW_OPERATORS +
    TIME_OPERATORS + CONSOLE_OPERATORS + ACCOUNT_OPERATORS +
    BLOCK_OPERATORS + TX_OPERATORS + TAG_OPERATORS + ACTOR_OPERATORS
)

DETERMINISTIC_BLOCKED_OPERATORS = frozenset(ACTOR_OPERATORS + CONSOLE_OPERATORS + TIME_OPERATORS)

def apply_operator(machine, symbol: Expr, stack: List[Expr], env) -> List[Expr]:
    if machine.mode == "deterministic" and symbol.value in DETERMINISTIC_BLOCKED_OPERATORS:
        machine.meter.charge_bytes(1)
        stack.append(NIL)
        return stack

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

    elif symbol.value == "closure":
        handle_stack_closure(machine, stack, env)

    elif symbol.value == "closure?":
        handle_stack_closure_with_result(machine, stack, env)

    elif symbol.value == "apply":
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
        return handle_stack_eval(machine, stack, env)

    elif symbol.value == "ref":
        handle_stack_ref(machine, stack, env)

    elif symbol.value == "load":
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
        return handle_stack_spawn(machine, stack, env)

    elif symbol.value == "send":
        return handle_stack_send(machine, stack)

    elif symbol.value == "receive":
        return handle_stack_receive(machine, stack)

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

    elif symbol.value == "time":
        handle_stack_time(machine, stack, env)

    elif symbol.value == "clock":
        handle_stack_clock(machine, stack, env)

    elif symbol.value == "concat":
        handle_stack_concat(machine, stack, env)

    elif symbol.value == "split":
        handle_stack_split(machine, stack, env)

    elif symbol.value == "index":
        handle_stack_index(machine, stack, env)

    elif symbol.value == "count":
        handle_stack_count(machine, stack, env)

    elif symbol.value == "reverse":
        handle_stack_reverse(machine, stack, env)

    elif symbol.value == "map":
        handle_stack_map(machine, stack, env)

    elif symbol.value == "filter":
        handle_stack_filter(machine, stack, env)

    elif symbol.value == "each":
        handle_stack_each(machine, stack, env)

    elif symbol.value == "fold":
        handle_stack_fold(machine, stack, env)

    elif symbol.value == "zip":
        handle_stack_zip(machine, stack, env)

    elif symbol.value == "find":
        handle_stack_find(machine, stack, env)

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

    elif symbol.value == "index?":
        handle_stack_index_with_result(machine, stack, env)

    elif symbol.value == "count?":
        handle_stack_count_with_result(machine, stack, env)

    elif symbol.value == "reverse?":
        handle_stack_reverse_with_result(machine, stack, env)

    elif symbol.value == "map?":
        handle_stack_map_with_result(machine, stack, env)

    elif symbol.value == "filter?":
        handle_stack_filter_with_result(machine, stack, env)

    elif symbol.value == "each?":
        handle_stack_each_with_result(machine, stack, env)

    elif symbol.value == "fold?":
        handle_stack_fold_with_result(machine, stack, env)

    elif symbol.value == "zip?":
        handle_stack_zip_with_result(machine, stack, env)

    elif symbol.value == "find?":
        handle_stack_find_with_result(machine, stack, env)

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

    elif symbol.value == "rec?":
        return handle_stack_rec_with_result(machine, stack, env)

    elif symbol.value == "if?":
        return handle_stack_if_with_result(machine, stack, env)

    elif symbol.value == "dip?":
        return handle_stack_dip_with_result(machine, stack, env)

    elif symbol.value == "eval?":
        return handle_stack_eval_with_result(machine, stack, env)

    elif symbol.value == "apply?":
        handle_stack_apply_with_result(machine, stack, env)

    elif symbol.value == "spawn?":
        return handle_stack_spawn_with_result(machine, stack, env)

    elif symbol.value == "send?":
        return handle_stack_send_with_result(machine, stack)

    elif symbol.value == "receive?":
        return handle_stack_receive_with_result(machine, stack)

    elif symbol.value == "block.bloom.insert?":
        handle_stack_block_bloom_insert_with_result(machine, stack, env)

    elif symbol.value == "match":
        return handle_stack_match(machine, stack, env)

    elif symbol.value == "is":
        handle_stack_is(machine, stack, env)

    return stack
