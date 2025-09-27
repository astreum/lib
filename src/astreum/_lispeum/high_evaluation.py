from typing import List, Union
import uuid

from src.astreum._lispeum import Env, Expr, Meter


def high_eval(self, env_id: uuid.UUID, expr: Expr, meter = None) -> Expr:

        if meter is None:
            meter = Meter()

        # ---------- atoms ----------
        if isinstance(expr, Expr.Error):
            return expr

        if isinstance(expr, Expr.Symbol):
            bound = self.env_get(env_id, expr.value.encode())
            if bound is None:
                return Expr.Error(f"unbound symbol '{expr.value}'", origin=expr)
            return bound

        if not isinstance(expr, Expr.ListExpr):
            return expr  # Expr.Byte or other literals passthrough

        # ---------- empty / single ----------
        if len(expr.elements) == 0:
            return expr
        if len(expr.elements) == 1:
            return self.high_eval(env_id=env_id, expr=expr.elements[0], meter=meter)

        tail = expr.elements[-1]

        # ---------- (value name def) ----------
        if isinstance(tail, Expr.Symbol) and tail.value == "def":
            if len(expr.elements) < 3:
                return Expr.Error("def expects (value name def)", origin=expr)
            name_e = expr.elements[-2]
            if not isinstance(name_e, Expr.Symbol):
                return Expr.Error("def name must be symbol", origin=name_e)
            value_e = expr.elements[-3]
            value_res = self.high_eval(env_id=env_id, expr=value_e, meter=meter)
            if isinstance(value_res, Expr.Error):
                return value_res
            self.env_set(env_id, name_e.value.encode(), value_res)
            return value_res

        # ---- LOW-LEVEL call: ( arg1 arg2 ... ( (body) sk ) ) ----
        if isinstance(tail, Expr.ListExpr):
            inner = tail.elements
            if len(inner) >= 2 and isinstance(inner[-1], Expr.Symbol) and inner[-1].value == "sk":
                body_expr = inner[-2]
                if not isinstance(body_expr, Expr.ListExpr):
                    return Expr.Error("sk body must be list", origin=body_expr)

                # helper: turn an Expr into a contiguous bytes buffer
                def to_bytes(v: Expr) -> Union[bytes, Expr.Error]:
                    if isinstance(v, Expr.Byte):
                        return bytes([v.value & 0xFF])
                    if isinstance(v, Expr.ListExpr):
                        # expect a list of Expr.Byte
                        out: bytearray = bytearray()
                        for el in v.elements:
                            if isinstance(el, Expr.Byte):
                                out.append(el.value & 0xFF)
                            else:
                                return Expr.Error("byte list must contain only Byte", origin=el)
                        return bytes(out)
                    if isinstance(v, Expr.Error):
                        return v
                    return Expr.Error("argument must resolve to Byte or (Byte ...)", origin=v)

                # resolve ALL preceding args into bytes (can be Byte or List[Byte])
                args_exprs = expr.elements[:-1]
                arg_bytes: List[bytes] = []
                for a in args_exprs:
                    v = self.high_eval(env_id=env_id, expr=a, meter=meter)
                    if isinstance(v, Expr.Error):
                        return v
                    vb = to_bytes(v)
                    if isinstance(vb, Expr.Error):
                        return vb
                    arg_bytes.append(vb)

                # build low-level code with $0-based placeholders ($0 = first arg)
                code: List[bytes] = []

                def emit(tok: Expr) -> Union[None, Expr.Error]:
                    if isinstance(tok, Expr.Symbol):
                        name = tok.value
                        if name.startswith("$"):
                            idx_s = name[1:]
                            if not idx_s.isdigit():
                                return Expr.Error("invalid sk placeholder", origin=tok)
                            idx = int(idx_s)  # $0 is first
                            if idx < 0 or idx >= len(arg_bytes):
                                return Expr.Error("arity mismatch in sk placeholder", origin=tok)
                            code.append(arg_bytes[idx])
                            return None
                        code.append(name.encode())
                        return None

                    if isinstance(tok, Expr.Byte):
                        code.append(bytes([tok.value & 0xFF]))
                        return None

                    if isinstance(tok, Expr.ListExpr):
                        rv = self.high_eval(env_id, tok, meter=meter)
                        if isinstance(rv, Expr.Error):
                            return rv
                        rb = to_bytes(rv)
                        if isinstance(rb, Expr.Error):
                            return rb
                        code.append(rb)
                        return None

                    if isinstance(tok, Expr.Error):
                        return tok

                    return Expr.Error("invalid token in sk body", origin=tok)

                for t in body_expr.elements:
                    err = emit(t)
                    if isinstance(err, Expr.Error):
                        return err

                # Execute low-level code built from sk-body using the caller's meter
                res = self.low_eval(code, meter=meter)
                if isinstance(res, Expr.Error):
                    return res
                return Expr.ListExpr([Expr.Byte(b) for b in res])

        # ---------- (... (body params fn))  HIGH-LEVEL CALL ----------
        if isinstance(tail, Expr.ListExpr):
            fn_form = tail
            if (len(fn_form.elements) >= 3
                and isinstance(fn_form.elements[-1], Expr.Symbol)
                and fn_form.elements[-1].value == "fn"):

                body_expr   = fn_form.elements[-3]
                params_expr = fn_form.elements[-2]

                if not isinstance(body_expr, Expr.ListExpr):
                    return Expr.Error("fn body must be list", origin=body_expr)
                if not isinstance(params_expr, Expr.ListExpr):
                    return Expr.Error("fn params must be list", origin=params_expr)

                params: List[bytes] = []
                for p in params_expr.elements:
                    if not isinstance(p, Expr.Symbol):
                        return Expr.Error("fn param must be symbol", origin=p)
                    params.append(p.value.encode())

                args_exprs = expr.elements[:-1]
                if len(args_exprs) != len(params):
                    return Expr.Error("arity mismatch", origin=expr)

                arg_bytes: List[bytes] = []
                for a in args_exprs:
                    v = self.high_eval(env_id, a, meter=meter)
                    if isinstance(v, Expr.Error):
                        return v
                    if not isinstance(v, Expr.Byte):
                        return Expr.Error("argument must resolve to Byte", origin=a)
                    arg_bytes.append(bytes([v.value & 0xFF]))

                # child env, bind params -> Expr.Byte
                child_env = uuid.uuid4()
                self.environments[child_env] = Env(parent_id=env_id)
                for name_b, val_b in zip(params, arg_bytes):
                    self.env_set(child_env, name_b, Expr.Byte(val_b[0]))

                # evaluate HL body, metered from the top
                return self.high_eval(child_env, body_expr, meter=meter)

        # ---------- default: resolve each element and return list ----------
        resolved: List[Expr] = [self.high_eval(env_id, e, meter=meter) for e in expr.elements]
        return Expr.ListExpr(resolved)