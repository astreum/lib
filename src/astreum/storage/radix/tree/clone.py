from __future__ import annotations

from ..node import clone_radix_node
from .model import RadixTree


def radix_tree_clone(tree: RadixTree) -> RadixTree:
    cloned = RadixTree(root_hash=None if tree.root_hash is None else tree.root_hash)
    cloned.nodes = {
        node_hash: clone_radix_node(node)
        for node_hash, node in tree.nodes.items()
    }
    return cloned
