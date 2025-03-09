"""
Storage utilities for Lispeum expressions.

This module provides functions to convert Lispeum expressions to an
object-based Merkle tree representation for storage and retrieval.
"""

import hashlib
import struct
from typing import Dict, Tuple, Any, List, Optional

from astreum.lispeum.expression import Expr


def expr_to_objects(expr: Any) -> Tuple[bytes, Dict[bytes, bytes]]:
    """
    Convert a Lispeum expression to a collection of objects in a Merkle tree structure.
    
    Args:
        expr: The expression to convert
        
    Returns:
        A tuple containing (root_hash, objects_dict) where:
        - root_hash is the hash of the root object
        - objects_dict is a dictionary mapping object hashes to their serialized representations
    """
    objects = {}
    root_hash = _serialize_expr(expr, objects)
    return root_hash, objects


def objects_to_expr(root_hash: bytes, objects: Dict[bytes, bytes]) -> Any:
    """
    Convert a collection of objects back to a Lispeum expression.
    
    Args:
        root_hash: The hash of the root object
        objects: A dictionary mapping object hashes to their serialized representations
        
    Returns:
        The reconstructed Lispeum expression
    """
    return _deserialize_expr(root_hash, objects)


def _serialize_expr(expr: Any, objects: Dict[bytes, bytes]) -> bytes:
    """
    Serialize a Lispeum expression to bytes and add it to the objects dictionary.
    
    Args:
        expr: The expression to serialize
        objects: Dictionary to store serialized objects
        
    Returns:
        The hash of the serialized expression
    """
    if expr is None:
        # None type
        type_bytes = b'N'  # N for None
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # None values don't need a value leaf, just return the type hash
        return type_hash
        
    elif isinstance(expr, Expr.ListExpr):
        # Create type leaf
        type_bytes = b'L'  # L for List
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Serialize each element and collect their hashes
        element_hashes = []
        for elem in expr.elements:
            elem_hash = _serialize_expr(elem, objects)
            element_hashes.append(elem_hash)
            
        # Create value leaf with all element hashes
        value_bytes = b''.join(element_hashes)
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.Symbol):
        # Create type leaf
        type_bytes = b'S'  # S for Symbol
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Create value leaf
        value_bytes = expr.value.encode('utf-8')
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.Integer):
        # Create type leaf
        type_bytes = b'I'  # I for Integer
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Create value leaf - use 2's complement little endian for integers
        value_bytes = struct.pack("<q", expr.value)  # 8-byte little endian
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.String):
        # Create type leaf
        type_bytes = b'T'  # T for Text/String
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Create value leaf
        value_bytes = expr.value.encode('utf-8')
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.Boolean):
        # Create type leaf
        type_bytes = b'B'  # B for Boolean
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Create value leaf
        value_bytes = b'1' if expr.value else b'0'
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.Function):
        # Create type leaf
        type_bytes = b'F'  # F for Function
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Serialize params
        params_list = []
        for param in expr.params:
            params_list.append(param.encode('utf-8'))
        params_bytes = b','.join(params_list)
        params_hash = hashlib.sha256(params_bytes).digest()
        objects[params_hash] = params_bytes
        
        # Serialize body recursively
        body_hash = _serialize_expr(expr.body, objects)
        
        # Combine params and body hashes for the value
        value_bytes = params_hash + body_hash
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    elif isinstance(expr, Expr.Error):
        # Create type leaf
        type_bytes = b'E'  # E for Error
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Serialize error components
        category_bytes = expr.category.encode('utf-8')
        category_hash = hashlib.sha256(category_bytes).digest()
        objects[category_hash] = category_bytes
        
        message_bytes = expr.message.encode('utf-8')
        message_hash = hashlib.sha256(message_bytes).digest()
        objects[message_hash] = message_bytes
        
        if expr.details:
            details_bytes = expr.details.encode('utf-8')
            details_hash = hashlib.sha256(details_bytes).digest()
            objects[details_hash] = details_bytes
            
            # Combine all three components
            value_bytes = category_hash + message_hash + details_hash
        else:
            # Just combine category and message
            value_bytes = category_hash + message_hash
            
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash
        
    else:
        # Unknown type - serialize as string
        type_bytes = b'U'  # U for Unknown
        type_hash = hashlib.sha256(type_bytes).digest()
        objects[type_hash] = type_bytes
        
        # Create value leaf with string representation
        value_bytes = str(expr).encode('utf-8')
        value_hash = hashlib.sha256(value_bytes).digest()
        objects[value_hash] = value_bytes
        
        # Create the tree node with type and value
        tree_bytes = type_hash + value_hash
        tree_hash = hashlib.sha256(tree_bytes).digest()
        objects[tree_hash] = tree_bytes
        
        return tree_hash


def _deserialize_expr(obj_hash: bytes, objects: Dict[bytes, bytes]) -> Any:
    """
    Deserialize a Lispeum expression from its hash.
    
    Args:
        obj_hash: The hash of the object to deserialize
        objects: Dictionary containing serialized objects
        
    Returns:
        The deserialized Lispeum expression
    """
    if obj_hash not in objects:
        return None
        
    obj_data = objects[obj_hash]
    
    # Check if this is a type-only node (for None)
    if len(obj_data) == 1:
        if obj_data == b'N':
            return None
        return None  # Unrecognized single-byte type
    
    # For regular nodes, expect 64 bytes (two 32-byte hashes)
    if len(obj_data) == 64:
        type_hash = obj_data[:32]
        value_hash = obj_data[32:]
        
        if type_hash not in objects or value_hash not in objects:
            return None
            
        type_data = objects[type_hash]
        value_data = objects[value_hash]
        
        # Switch based on the type marker
        if type_data == b'L':  # List
            elements = []
            # Each hash is 32 bytes
            hash_size = 32
            for i in range(0, len(value_data), hash_size):
                elem_hash = value_data[i:i+hash_size]
                if elem_hash:
                    elem = _deserialize_expr(elem_hash, objects)
                    elements.append(elem)
            return Expr.ListExpr(elements)
            
        elif type_data == b'S':  # Symbol
            return Expr.Symbol(value_data.decode('utf-8'))
            
        elif type_data == b'I':  # Integer
            int_value = struct.unpack("<q", value_data)[0]
            return Expr.Integer(int_value)
            
        elif type_data == b'T':  # String (Text)
            return Expr.String(value_data.decode('utf-8'))
            
        elif type_data == b'B':  # Boolean
            return Expr.Boolean(value_data == b'1')
            
        elif type_data == b'F':  # Function
            # Value contains params_hash and body_hash
            params_hash = value_data[:32]
            body_hash = value_data[32:]
            
            if params_hash not in objects:
                return None
                
            params_data = objects[params_hash]
            params = [p.decode('utf-8') for p in params_data.split(b',') if p]
            
            body = _deserialize_expr(body_hash, objects)
            return Expr.Function(params, body)
            
        elif type_data == b'E':  # Error
            # Check if we have details or just category and message
            if len(value_data) == 64:  # No details
                category_hash = value_data[:32]
                message_hash = value_data[32:]
                details_hash = None
            elif len(value_data) == 96:  # With details
                category_hash = value_data[:32]
                message_hash = value_data[32:64]
                details_hash = value_data[64:]
            else:
                return None
                
            if category_hash not in objects or message_hash not in objects:
                return None
                
            category = objects[category_hash].decode('utf-8')
            message = objects[message_hash].decode('utf-8')
            
            details = None
            if details_hash and details_hash in objects:
                details = objects[details_hash].decode('utf-8')
                
            return Expr.Error(category, message, details)
            
        elif type_data == b'U':  # Unknown
            return Expr.String(value_data.decode('utf-8'))
            
    return None  # Unrecognized format


def store_expr(expr: Any, storage) -> bytes:
    """
    Store a Lispeum expression in the provided storage.
    
    Args:
        expr: The expression to store
        storage: Storage interface with put(key, value) method
        
    Returns:
        The hash of the root object
    """
    root_hash, objects = expr_to_objects(expr)
    
    # Store all objects in the storage
    for obj_hash, obj_data in objects.items():
        storage.put(obj_hash, obj_data)
        
    return root_hash


def get_expr_from_storage(root_hash: bytes, storage) -> Any:
    """
    Load a Lispeum expression from storage.
    
    Args:
        root_hash: The hash of the root object
        storage: Storage interface with get(key) method
        
    Returns:
        The loaded Lispeum expression, or None if not found
    """
    if not root_hash:
        return None
        
    # Build the objects dictionary from storage
    objects = {}
    queue = [root_hash]
    visited = set()
    
    while queue:
        current_hash = queue.pop(0)
        if current_hash in visited:
            continue
            
        visited.add(current_hash)
        obj_data = storage.get(current_hash)
        
        if not obj_data:
            # Can't find an object, return None
            return None
            
        objects[current_hash] = obj_data
        
        # For single-byte nodes (e.g., None), no further processing needed
        if len(obj_data) == 1:
            continue
            
        # For regular tree nodes (type + value)
        if len(obj_data) == 64:
            # Add both hashes to the queue
            type_hash = obj_data[:32]
            value_hash = obj_data[32:]
            
            if type_hash not in visited:
                queue.append(type_hash)
                
            if value_hash not in visited:
                queue.append(value_hash)
                
            # For function and error types, we need to check the value fields
            # which might contain additional hashes
            if type_hash in objects:
                type_data = objects[type_hash]
                
                # For Function type, the value contains params_hash + body_hash
                if type_data == b'F' and value_hash in objects:
                    value_data = objects[value_hash]
                    if len(value_data) == 64:
                        params_hash = value_data[:32]
                        body_hash = value_data[32:]
                        
                        if params_hash not in visited:
                            queue.append(params_hash)
                            
                        if body_hash not in visited:
                            queue.append(body_hash)
                
                # For Error type, the value contains category_hash + message_hash + [details_hash]
                elif type_data == b'E' and value_hash in objects:
                    value_data = objects[value_hash]
                    hash_size = 32
                    
                    for i in range(0, len(value_data), hash_size):
                        component_hash = value_data[i:i+hash_size]
                        if component_hash and component_hash not in visited:
                            queue.append(component_hash)
                
                # For List type, the value contains all element hashes
                elif type_data == b'L' and value_hash in objects:
                    value_data = objects[value_hash]
                    hash_size = 32
                    
                    for i in range(0, len(value_data), hash_size):
                        elem_hash = value_data[i:i+hash_size]
                        if elem_hash and elem_hash not in visited:
                            queue.append(elem_hash)
    
    # Reconstruct the expression from objects
    return objects_to_expr(root_hash, objects)
