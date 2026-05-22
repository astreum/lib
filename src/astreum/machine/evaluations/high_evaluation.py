from typing import List, Optional, Union
import uuid

from ..models.environment import Env
from ..models.expression import Expr, error_expr, ERROR_SYMBOL
from ..models.meter import Meter


RESERVED_SYMBOL_PREFIXES = ("tx.", "acc.")


def _is_error(expr: Expr) -> bool:
    return (
        isinstance(expr, Expr.ListExpr)
        and bool(expr.elements)
        and isinstance(expr.elements[0], Expr.Symbol)
        and expr.elements[0].value == ERROR_SYMBOL
    )


def _hex_symbol_to_bytes(value: Optional[str]) -> Optional[bytes]:
    if not value:
        return None
    data = value.strip()
    if data.startswith(("0x", "0X")):
        data = data[2:]
    if len(data) % 2:
        data = "0" + data
    try:
        return bytes.fromhex(data)
    except ValueError:
        return None


def _expr_to_bytes(expr: Expr) -> Optional[bytes]:
    if isinstance(expr, Expr.Bytes):
        return expr.value
    if isinstance(expr, Expr.Symbol):
        return _hex_symbol_to_bytes(expr.value)
    return None


def _eval_sk_call(self, env_id, meter, tail: Expr.ListExpr, args_exprs: List[Expr]) -> Expr:
    """Evaluate an sk call: tail = ((body) sk), args_exprs = preceding elements."""
    inner = tail.elements
    body_expr = inner[-2]
    if not isinstance(body_expr, Expr.ListExpr):
        return error_expr("eval", "sk body must be list")

    def to_bytes(v: Expr) -> Union[bytes, Expr]:
        if isinstance(v, Expr.Bytes):
            return v.value
        if isinstance(v, Expr.ListExpr):
            out: bytearray = bytearray()
            for el in v.elements:
                if isinstance(el, Expr.Bytes):
                    out.extend(el.value)
                else:
                    return error_expr("eval", "byte list must contain only Bytes elements")
            return bytes(out)
        if _is_error(v):
            return v
        return error_expr("eval", "argument must resolve to Bytes or (Bytes ...)")

    arg_bytes: List[bytes] = []
    for a in args_exprs:
        v = self.high_eval(expr=a, env_id=env_id, meter=meter)
        if _is_error(v):
            return v
        vb = to_bytes(v)
        if not isinstance(vb, bytes):
            if _is_error(vb):
                return vb
            return error_expr("eval", "unexpected expression while coercing to bytes")
        arg_bytes.append(vb)

    code: List[bytes] = []

    def emit(tok: Expr) -> Union[None, Expr]:
        if isinstance(tok, Expr.Symbol):
            name = tok.value
            if name.startswith("$"):
                idx_s = name[1:]
                if not idx_s.isdigit():
                    return error_expr("eval", "invalid sk placeholder")
                idx = int(idx_s)
                if idx < 0 or idx >= len(arg_bytes):
                    return error_expr("eval", "arity mismatch in sk placeholder")
                code.append(arg_bytes[idx])
                return None
            code.append(name.encode())
            return None
        if isinstance(tok, Expr.Bytes):
            code.append(tok.value)
            return None
        if isinstance(tok, Expr.ListExpr):
            rv = self.high_eval(expr=tok, env_id=env_id, meter=meter)
            if _is_error(rv):
                return rv
            rb = to_bytes(rv)
            if not isinstance(rb, bytes):
                if _is_error(rb):
                    return rb
                return error_expr("eval", "unexpected expression while coercing list token to bytes")
            code.append(rb)
            return None
        if _is_error(tok):
            return tok
        return error_expr("eval", "invalid token in sk body")

    for t in body_expr.elements:
        err = emit(t)
        if err is not None and _is_error(err):
            return err

    res = self.low_eval(code, meter=meter)
    return res


def _eval_fn_call(self, env_id, meter, fn_form: Expr.ListExpr, args_exprs: List[Expr]) -> Expr:
    """Evaluate an fn call: fn_form = ((body) (params) fn), args_exprs = preceding elements."""
    body_expr   = fn_form.elements[-3]
    params_expr = fn_form.elements[-2]

    if not isinstance(body_expr, Expr.ListExpr):
        return error_expr("eval", "fn body must be list")
    if not isinstance(params_expr, Expr.ListExpr):
        return error_expr("eval", "fn params must be list")

    params: List[str] = []
    for p in params_expr.elements:
        if not isinstance(p, Expr.Symbol):
            return error_expr("eval", "fn param must be symbol")
        params.append(p.value)

    if len(args_exprs) != len(params):
        return error_expr("eval", "arity mismatch")

    arg_bytes: List[bytes] = []
    for a in args_exprs:
        v = self.high_eval(expr=a, env_id=env_id, meter=meter)
        if _is_error(v):
            return v
        if not isinstance(v, Expr.Bytes):
            return error_expr("eval", "argument must resolve to Bytes")
        arg_bytes.append(v.value)

    child_env = uuid.uuid4()
    self.environments[child_env] = Env(parent_id=env_id)
    try:
        for name_b, val_b in zip(params, arg_bytes):
            self.env_set(child_env, name_b, Expr.Bytes(val_b))
        return self.high_eval(expr=body_expr, env_id=child_env, meter=meter)
    finally:
        self.environments.pop(child_env, None)


def high_eval(self, expr: Expr, env_id: Optional[uuid.UUID] = None, meter = None) -> Expr:
    """Evaluate high-level expressions with scoped environments and metering."""
    if meter is None:
        meter = Meter()

    call_env_id = uuid.uuid4()
    self.environments[call_env_id] = Env(parent_id=env_id)
    env_id = call_env_id

    try:
        # ---------- atoms ----------
        if _is_error(expr):
            return expr

        if isinstance(expr, Expr.Symbol):
            bound = self.env_get(env_id, expr.value)
            if bound is None:
                return error_expr("eval", f"unbound symbol '{expr.value}'")
            return bound

        if not isinstance(expr, Expr.ListExpr):
            return expr  # Expr.Bytes or other literals passthrough

        # ---------- empty / single ----------
        if len(expr.elements) == 0:
            return expr
        if len(expr.elements) == 1:
            return self.high_eval(expr=expr.elements[0], env_id=env_id, meter=meter)

        tail = expr.elements[-1]

        # ---------- (value name def) ----------
        if isinstance(tail, Expr.Symbol) and tail.value == "def":
            if len(expr.elements) < 3:
                return error_expr("eval", "def expects (value name def)")
            name_e = expr.elements[-2]
            if not isinstance(name_e, Expr.Symbol):
                return error_expr("eval", "def name must be symbol")
            if name_e.value.startswith(RESERVED_SYMBOL_PREFIXES):
                return error_expr("eval", "cannot bind reserved symbol")
            value_e = expr.elements[-3]
            value_res = self.high_eval(expr=value_e, env_id=env_id, meter=meter)
            if _is_error(value_res):
                return value_res
            self.env_set(call_env_id, name_e.value, value_res)
            return value_res
        
        # Reference Call
        # (atom_id ref)
        if isinstance(tail, Expr.Symbol) and tail.value == "ref":
            if len(expr.elements) != 2:
                return error_expr("eval", "ref expects (atom_id ref)")
            key_bytes = _expr_to_bytes(expr.elements[0])
            if not key_bytes:
                return error_expr("eval", "ref expects (atom_id ref)")
            stored_list = self.get_expr_list_from_storage(key_bytes)
            if stored_list is None:
                return error_expr("eval", "ref target not found")
            return stored_list

        # Eval Call
        # (expr eval) — evaluate expr with high_eval
        if isinstance(tail, Expr.Symbol) and tail.value == "eval":
            if len(expr.elements) != 2:
                return error_expr("eval", "eval expects (expr eval)")
            return self.high_eval(expr=expr.elements[0], env_id=env_id, meter=meter)

        # Expression account control constructors. These are inert values for
        # the evaluator; the expression account call handler applies effects.
        if isinstance(tail, Expr.Symbol) and tail.value == "acc.pay":
            if len(expr.elements) != 4:
                return error_expr("eval", "acc.pay expects (recipient amount next-expr acc.pay)")
            recipient_res = self.high_eval(expr=expr.elements[0], env_id=env_id, meter=meter)
            if _is_error(recipient_res):
                return recipient_res
            amount_res = self.high_eval(expr=expr.elements[1], env_id=env_id, meter=meter)
            if _is_error(amount_res):
                return amount_res
            return Expr.ListExpr([
                recipient_res,
                amount_res,
                expr.elements[2],
                Expr.Symbol("acc.pay"),
            ])

        if isinstance(tail, Expr.Symbol) and tail.value == "acc.get":
            if len(expr.elements) != 4:
                return error_expr("eval", "acc.get expects (key found-next missing-next acc.get)")
            key_res = self.high_eval(expr=expr.elements[0], env_id=env_id, meter=meter)
            if _is_error(key_res):
                return key_res
            return Expr.ListExpr([
                key_res,
                expr.elements[1],
                expr.elements[2],
                Expr.Symbol("acc.get"),
            ])

        if isinstance(tail, Expr.Symbol) and tail.value == "acc.put":
            if len(expr.elements) != 4:
                return error_expr("eval", "acc.put expects (key value next-expr acc.put)")
            key_res = self.high_eval(expr=expr.elements[0], env_id=env_id, meter=meter)
            if _is_error(key_res):
                return key_res
            value_res = self.high_eval(expr=expr.elements[1], env_id=env_id, meter=meter)
            if _is_error(value_res):
                return value_res
            return Expr.ListExpr([
                key_res,
                value_res,
                expr.elements[2],
                Expr.Symbol("acc.put"),
            ])

        # ---------- evaluate tail for function dispatch ----------
        # Resolve the tail (Symbol → env lookup, or inline ListExpr passthrough).
        # If it resolves to an sk or fn function value, dispatch the call.
        # This unifies inline ((body) sk) and named (sub) function calls.
        tail_val = self.high_eval(expr=tail, env_id=env_id, meter=meter)
        if _is_error(tail_val):
            return tail_val

        if isinstance(tail_val, Expr.ListExpr):
            inner = tail_val.elements
            if len(inner) >= 2 and isinstance(inner[-1], Expr.Symbol):
                tag = inner[-1].value
                args_exprs = expr.elements[:-1]
                if tag == "sk":
                    return _eval_sk_call(self, env_id, meter, tail_val, args_exprs)
                elif tag == "fn":
                    return _eval_fn_call(self, env_id, meter, tail_val, args_exprs)

        # ---------- default: resolve each element and return list ----------
        resolved: List[Expr] = [self.high_eval(expr=e, env_id=env_id, meter=meter) for e in expr.elements]
        return Expr.ListExpr(resolved)
    finally:
        self.environments.pop(call_env_id, None)
