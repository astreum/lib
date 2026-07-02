from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib import request as _urllib_request

from astreum.machine import Env, Expr, parse, tokenize


def compile(
    node: object,
    script: str,
    target: str,
) -> Env:
    """Returns an Env with a target definition and all of the definitions
    it transitively depends on.  Only the definitions actually referenced
    by the target (including imported modules when they are referenced using
    dot-prefixed symbols in the target) are included.  Modules that are not
    needed are never parsed.

    Parameters
    ----------
    node:
        An Astreum ``Node`` instance (``None`` is accepted when only
        file-based imports are used).
    script:
        Path to the root ``.aex`` script file (absolute or relative).
    target:
        Name of the definition to resolve.  May include dots for imported
        modules, e.g. ``"math.calc_sum"``.
    """
    env_data: Dict[str, Expr] = {}
    visited: Set[Tuple[str, str, Tuple[str, ...]]] = set()
    cache: Dict[str, Tuple[Dict[str, Expr], Dict[str, str]]] = {}

    module_id = _resolve_identity(script, None)

    if "." in target:
        parts = target.split(".")
        _resolve_name_chain(
            node=node, module_id=module_id, name_parts=parts,
            prefix_chain=(), env_data=env_data, visited=visited, cache=cache,
        )
    else:
        _resolve_def(
            node=node, module_id=module_id, name=target,
            prefix_chain=(), env_data=env_data, visited=visited, cache=cache,
        )

    return Env(data=env_data)


# ---------------------------------------------------------------------------
# URL fetch
# ---------------------------------------------------------------------------

def _fetch_url(url: str) -> str:
    with _urllib_request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8")


# ---------------------------------------------------------------------------
# Identity resolution
# ---------------------------------------------------------------------------

def _resolve_identity(path_str: str, from_dir: Optional[Path]) -> str:
    if path_str.startswith(("http://", "https://")):
        return path_str

    p = Path(path_str).expanduser()
    if not p.is_absolute() and from_dir is not None:
        p = (from_dir / p).resolve()
    else:
        p = p.resolve()

    return str(p)


# ---------------------------------------------------------------------------
# Prefix joining
# ---------------------------------------------------------------------------

def _join_prefixes(chain: Tuple[str, ...], name: str) -> str:
    if not chain:
        return name
    return ".".join(chain) + "." + name


# ---------------------------------------------------------------------------
# Link → list helper
# ---------------------------------------------------------------------------

def _link_to_list(link: Expr) -> List[Expr]:
    result: List[Expr] = []
    while link._tag == "link":
        if link._head is None and link._tail is None:
            break
        result.append(link._head)
        link = link._tail
    return result


# ---------------------------------------------------------------------------
# Path extraction from import expr  (Symbol value or Bytes decoded as utf-8)
# ---------------------------------------------------------------------------

def _path_from_expr(expr: Expr) -> str:
    if expr._tag == "symbol":
        return _strip_quotes(expr.value)
    if expr._tag == "bytes":
        return expr.value.decode("utf-8")
    raise ValueError(f"import path must be a symbol or bytes, got {expr._tag}")


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


# ---------------------------------------------------------------------------
# Module parsing (cached)
# ---------------------------------------------------------------------------

def _parse_module(
    identity: str,
    cache: Dict[str, Tuple[Dict[str, Expr], Dict[str, str]]],
) -> Tuple[Dict[str, Expr], Dict[str, str]]:
    if identity in cache:
        return cache[identity]

    if identity.startswith(("http://", "https://")):
        text = _fetch_url(identity)
        mod_dir = None
    else:
        try:
            text = Path(identity).read_text(encoding="utf-8")
        except OSError as exc:
            raise RuntimeError(f"unable to read module at '{identity}'") from exc
        mod_dir = Path(identity).parent

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    tokens = tokenize(text)

    defs: Dict[str, Expr] = {}
    imports: Dict[str, str] = {}

    remaining = tokens
    while remaining:
        expr, remaining = parse(tokens=remaining)
        elems = _link_to_list(expr)

        if len(elems) != 3:
            raise ValueError(f"definition must have 3 elements, got {len(elems)}")

        first, second, terminator = elems
        if not terminator._tag == "symbol":
            raise ValueError("definition must terminate with a symbol")

        if terminator.value == "def":
            if not second._tag == "symbol":
                raise ValueError("def name must be a symbol")
            defs[second.value] = first

        elif terminator.value == "import":
            if not first._tag == "symbol":
                raise ValueError("import prefix must be a symbol")
            path_str = _path_from_expr(second)
            imports[first.value] = _resolve_identity(path_str, mod_dir)

        else:
            raise ValueError(
                f"definition must terminate with def or import, got '{terminator.value}'"
            )

    if not defs and not imports:
        raise ValueError(f"module '{identity}' contains no definitions or imports")

    cache[identity] = (defs, imports)
    return defs, imports


# ---------------------------------------------------------------------------
# resolve  –  tree-shaking entry per target def
# ---------------------------------------------------------------------------

def _resolve_def(
    node,
    module_id: str,
    name: str,
    prefix_chain: Tuple[str, ...],
    env_data: Dict[str, Expr],
    visited: Set[Tuple[str, str, Tuple[str, ...]]],
    cache: Dict[str, Tuple[Dict[str, Expr], Dict[str, str]]],
) -> None:
    vkey = (module_id, name, prefix_chain)
    if vkey in visited:
        return
    visited.add(vkey)

    defs, imports = _parse_module(module_id, cache)

    if name not in defs:
        raise ValueError(f"definition '{name}' not found in '{module_id}'")

    body = defs[name]
    qualified = _join_prefixes(prefix_chain, name)
    env_data[qualified] = body

    _walk_body(
        body,
        module_id=module_id,
        prefix_chain=prefix_chain,
        defs=defs,
        imports=imports,
        env_data=env_data,
        visited=visited,
        cache=cache,
        node=node,
    )


def _resolve_name_chain(
    node,
    module_id: str,
    name_parts: List[str],
    prefix_chain: Tuple[str, ...],
    env_data: Dict[str, Expr],
    visited: Set[Tuple[str, str, Tuple[str, ...]]],
    cache: Dict[str, Tuple[Dict[str, Expr], Dict[str, str]]],
) -> None:
    first, *rest = name_parts
    defs, imports = _parse_module(module_id, cache)

    if rest:
        if first not in imports:
            raise ValueError(f"import prefix '{first}' not found in '{module_id}'")
        next_id = imports[first]
        new_chain = prefix_chain + (first,)
        _resolve_name_chain(
            node=node, module_id=next_id, name_parts=rest,
            prefix_chain=new_chain, env_data=env_data,
            visited=visited, cache=cache,
        )
    else:
        _resolve_def(
            node=node, module_id=module_id, name=first,
            prefix_chain=prefix_chain, env_data=env_data,
            visited=visited, cache=cache,
        )


def _walk_body(
    expr: Expr,
    module_id: str,
    prefix_chain: Tuple[str, ...],
    defs: Dict[str, Expr],
    imports: Dict[str, str],
    env_data: Dict[str, Expr],
    visited: Set[Tuple[str, str, Tuple[str, ...]]],
    cache: Dict[str, Tuple[Dict[str, Expr], Dict[str, str]]],
    node,
) -> None:
    if expr._tag == "symbol":
        sym = expr.value
        if "." in sym:
            parts = sym.split(".")
            first, rest = parts[0], parts[1:]
            if first in imports:
                next_id = imports[first]
                new_chain = prefix_chain + (first,)
                _resolve_name_chain(
                    node=node, module_id=next_id, name_parts=rest,
                    prefix_chain=new_chain, env_data=env_data,
                    visited=visited, cache=cache,
                )
        elif sym in defs:
            _resolve_def(
                node=node, module_id=module_id, name=sym,
                prefix_chain=prefix_chain, env_data=env_data,
                visited=visited, cache=cache,
            )

    elif expr._tag == "link":
        if expr._head is not None:
            _walk_body(
                expr._head, module_id=module_id, prefix_chain=prefix_chain,
                defs=defs, imports=imports, env_data=env_data,
                visited=visited, cache=cache, node=node,
            )
        if expr._tail is not None:
            _walk_body(
                expr._tail, module_id=module_id, prefix_chain=prefix_chain,
                defs=defs, imports=imports, env_data=env_data,
                visited=visited, cache=cache, node=node,
            )



