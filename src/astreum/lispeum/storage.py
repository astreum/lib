"""
Storage utilities for Lispeum expressions.

This module provides functions to convert Lispeum expressions to an
object-based Merkle tree representation for storage and retrieval.
"""

import struct
from typing import Dict, Tuple, Any, List, Optional

from astreum.lispeum.expression import Expr
from ..crypto.blake30 import hash_data


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
        is_leaf = True
        type_bytes = b'N'  # N for None
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.ListExpr):
        # Create type object
        is_leaf = False
        type_bytes = b'L'  # L for List
        
        # Serialize each element and collect their hashes
        element_hashes = []
        for elem in expr.elements:
            elem_hash = _serialize_expr(elem, objects)
            element_hashes.append(elem_hash)
        
        # Create value leaf with all element hashes
        value_bytes = b''.join(element_hashes)
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.Symbol):
        # Create the object - symbols are leaf nodes
        is_leaf = True
        type_bytes = b'S'  # S for Symbol
        value_bytes = expr.value.encode('utf-8')
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.Integer):
        # Create the object - integers are leaf nodes
        is_leaf = True
        type_bytes = b'I'  # I for Integer
        value_bytes = struct.pack("<q", expr.value)  # 8-byte little endian
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.String):
        # Create the object - strings are leaf nodes
        is_leaf = True
        type_bytes = b'T'  # T for Text/String
        value_bytes = expr.value.encode('utf-8')
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.Boolean):
        # Create the object - booleans are leaf nodes
        is_leaf = True
        type_bytes = b'B'  # B for Boolean
        value_bytes = b'1' if expr.value else b'0'
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.Function):
        # Create the object - functions are not leaf nodes
        is_leaf = False
        type_bytes = b'F'  # F for Function
        
        # Serialize params
        params_list = []
        for param in expr.params:
            params_list.append(param.encode('utf-8'))
        params_bytes = b','.join(params_list)
        
        # Serialize body recursively
        body_hash = _serialize_expr(expr.body, objects)
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + params_bytes + body_hash
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
        
    elif isinstance(expr, Expr.Error):
        # Create the object - errors are not leaf nodes
        is_leaf = False
        type_bytes = b'E'  # E for Error
        
        # Serialize error components
        category_bytes = expr.category.encode('utf-8')
        message_bytes = expr.message.encode('utf-8')
        details_bytes = b'' if expr.details is None else expr.details.encode('utf-8')
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + category_bytes + b'\0' + message_bytes + b'\0' + details_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash
    
    else:
        # Default fallback for unknown types
        is_leaf = True
        type_bytes = b'U'  # U for Unknown
        value_bytes = str(expr).encode('utf-8')
        
        # Create the object with leaf flag and body
        object_bytes = struct.pack("?", is_leaf) + type_bytes + value_bytes
        object_hash = hash_data(object_bytes)
        objects[object_hash] = object_bytes
        
        return object_hash


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
        
    obj_bytes = objects[obj_hash]
    
    # Extract leaf flag
    is_leaf = struct.unpack("?", obj_bytes[0:1])[0]
    
    # Get type indicator
    type_indicator = obj_bytes[1:2]
    
    # Deserialize based on type
    if type_indicator == b'N':  # None
        return None
        
    elif type_indicator == b'L':  # List
        if is_leaf:
            # Empty list
            return Expr.ListExpr([])
        
        # Non-leaf list has child element hashes
        elements_bytes = obj_bytes[2:]
        element_hashes = [elements_bytes[i:i+32] for i in range(0, len(elements_bytes), 32)]
        
        # Deserialize each element
        elements = []
        for elem_hash in element_hashes:
            elem = _deserialize_expr(elem_hash, objects)
            elements.append(elem)
            
        return Expr.ListExpr(elements)
        
    elif type_indicator == b'S':  # Symbol
        value_bytes = obj_bytes[2:]
        return Expr.Symbol(value_bytes.decode('utf-8'))
        
    elif type_indicator == b'I':  # Integer
        value_bytes = obj_bytes[2:10]  # 8 bytes for int64
        value = struct.unpack("<q", value_bytes)[0]
        return Expr.Integer(value)
        
    elif type_indicator == b'T':  # Text/String
        value_bytes = obj_bytes[2:]
        return Expr.String(value_bytes.decode('utf-8'))
        
    elif type_indicator == b'B':  # Boolean
        value_bytes = obj_bytes[2:3]
        return Expr.Boolean(value_bytes == b'1')
        
    elif type_indicator == b'F':  # Function
        # Non-leaf function
        remaining_bytes = obj_bytes[2:]
        
        # Find the separator between params and body hash
        params_end = remaining_bytes.find(b',', remaining_bytes.rfind(b','))
        if params_end == -1:
            params_end = 0  # No params
            
        params_bytes = remaining_bytes[:params_end+1]
        body_hash = remaining_bytes[params_end+1:]
        
        # Parse params
        params = []
        if params_bytes:
            for param_bytes in params_bytes.split(b','):
                if param_bytes:  # Skip empty strings
                    params.append(param_bytes.decode('utf-8'))
        
        # Deserialize body
        body = _deserialize_expr(body_hash, objects)
        
        return Expr.Function(params, body)
        
    elif type_indicator == b'E':  # Error
        remaining_bytes = obj_bytes[2:]
        
        # Split by null bytes to get category, message, and details
        parts = remaining_bytes.split(b'\0', 2)
        
        category = parts[0].decode('utf-8')
        message = parts[1].decode('utf-8') if len(parts) > 1 else ""
        details = parts[2].decode('utf-8') if len(parts) > 2 else None
        
        return Expr.Error(category, message, details)
        
    else:  # Unknown
        value_bytes = obj_bytes[2:]
        # Return as a string
        return value_bytes.decode('utf-8')


def store_expr(expr: Any, storage) -> bytes:
    """
    Store a Lispeum expression in the provided storage.
    
    Args:
        expr: The expression to store
        storage: Storage interface with put(key, value) method
        
    Returns:
        The hash of the root object
    """
    # Convert expression to objects
    root_hash, objects = expr_to_objects(expr)
    
    # Store each object in the storage
    for obj_hash, obj_data in objects.items():
        storage.put(obj_hash, obj_data)
    
    return root_hash


def get_expr_from_storage(root_hash: bytes, storage, max_depth: int = 50) -> Any:
    """
    Load a Lispeum expression from storage. Will recursively resolve
    objects from the storage until a leaf node is reached.
    
    Args:
        root_hash: The hash of the root object
        storage: Storage interface with get method and get_recursive method
        max_depth: Maximum recursion depth for resolution
        
    Returns:
        The loaded Lispeum expression, or None if not found
    """
    # Check if storage has the get_recursive method (newer storage interface)
    if hasattr(storage, 'get_recursive'):
        # Use the storage's built-in recursive retrieval
        objects = storage.get_recursive(root_hash, max_depth)
    else:
        # Fallback to manual recursive retrieval for older storage interfaces
        objects = {}
        _load_objects_recursive(root_hash, storage, objects, max_depth)
    
    # If no objects were retrieved, return None
    if not objects:
        return None
        
    # Deserialize the expression
    return objects_to_expr(root_hash, objects)


def _load_objects_recursive(obj_hash: bytes, storage, objects: Dict[bytes, bytes], max_depth: int, current_depth: int = 0) -> bool:
    """
    Recursively load objects from storage.
    
    Args:
        obj_hash: The hash of the object to load
        storage: Storage interface with get(key) method
        objects: Dictionary to store loaded objects
        max_depth: Maximum recursion depth
        current_depth: Current recursion depth
        
    Returns:
        True if object was loaded, False otherwise
    """
    # Check if we've reached max recursion depth
    if current_depth >= max_depth:
        print(f"Warning: Max recursion depth {max_depth} reached while loading objects")
        return False
        
    # Check if we already have this object
    if obj_hash in objects:
        return True
        
    # Load the object from storage
    obj_data = storage.get(obj_hash)
    if obj_data is None:
        return False
        
    # Store the object
    objects[obj_hash] = obj_data
    
    # Check if this is a leaf node
    is_leaf = struct.unpack("?", obj_data[0:1])[0]
    if is_leaf:
        # Leaf node, no need to recurse
        return True
        
    # For non-leaf nodes, recursively load child objects
    type_indicator = obj_data[1:2]
    
    if type_indicator == b'L':  # List
        # Non-leaf list has child element hashes
        elements_bytes = obj_data[2:]
        element_hashes = [elements_bytes[i:i+32] for i in range(0, len(elements_bytes), 32)]
        
        # Load each element
        for elem_hash in element_hashes:
            _load_objects_recursive(elem_hash, storage, objects, max_depth, current_depth + 1)
            
    elif type_indicator == b'F':  # Function
        # Non-leaf function has body hash
        remaining_bytes = obj_data[2:]
        
        # Find the separator between params and body hash
        params_end = remaining_bytes.find(b',', remaining_bytes.rfind(b','))
        if params_end == -1:
            params_end = 0  # No params
            
        body_hash = remaining_bytes[params_end+1:]
        
        # Load body
        _load_objects_recursive(body_hash, storage, objects, max_depth, current_depth + 1)
    
    return True
