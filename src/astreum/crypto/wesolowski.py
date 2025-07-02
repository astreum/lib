import hashlib
from typing import Tuple
from quadratic_form import QuadraticForm

# --- Helper functions ---------------------------------------------------

def hash_to_int(*args: bytes) -> int:
    """
    Hash the concatenation of args (bytes) to a large integer using SHA-256.
    """
    h = hashlib.sha256()
    for b in args:
        h.update(b)
    return int.from_bytes(h.digest(), 'big')

# --- Class-group VDF functions using QuadraticForm ----------------------

def group_mul(x: QuadraticForm, y: QuadraticForm) -> QuadraticForm:
    """
    Compose two class-group elements via QuadraticForm multiplication.
    """
    return (x * y)


def identity(D: int) -> QuadraticForm:
    """
    Return the identity element of the class group for discriminant D.
    """
    # For D ≡ 1 mod 4, identity form is (1, 1, (1-D)//4)
    b0 = 1
    c0 = (b0*b0 - D) // 4
    return QuadraticForm(1, b0, c0, D)


def class_group_square(x: QuadraticForm) -> QuadraticForm:
    """
    One sequential squaring step in the class group.
    """
    return group_mul(x, x)


def group_exp(x: QuadraticForm, exponent: int) -> QuadraticForm:
    """
    Fast exponentiation in the class group by repeated squaring.
    """
    result = identity(x.D)
    base = x
    e = exponent
    while e > 0:
        if e & 1:
            result = group_mul(result, base)
        base = group_mul(base, base)
        e >>= 1
    return result

# --- Wesolowski proof and verify ----------------------------------------

def compute_wesolowski_proof(
    x0: QuadraticForm,
    y: QuadraticForm,
    T: int
) -> QuadraticForm:
    """
    Compute the Wesolowski proof π for VDF evaluation:
    Solve 2^T = c * q + r, where
      c = hash(x0 || y || T)
    Return π = x0^q in the class group.
    """
    # Derive challenge c
    h_bytes = serialize(x0) + serialize(y) + T.to_bytes((T.bit_length()+7)//8, 'big')
    c = hash_to_int(h_bytes)
    # Divide exponent
    two_T = 1 << T
    q, r = divmod(two_T, c)
    # π = x0^q
    return group_exp(x0, q)


def verify_wesolowski_proof(
    x0: QuadraticForm,
    y: QuadraticForm,
    pi: QuadraticForm,
    T: int
) -> bool:
    """
    Verify π satisfies: π^c * x0^r == y.
    """
    h_bytes = serialize(x0) + serialize(y) + T.to_bytes((T.bit_length()+7)//8, 'big')
    c = hash_to_int(h_bytes)
    two_T = 1 << T
    q, r = divmod(two_T, c)
    lhs = group_mul(group_exp(pi, c), group_exp(x0, r))
    return lhs == y

# --- Serialization helpers ----------------------------------------------

def serialize(x: QuadraticForm) -> bytes:
    """
    Serialize a QuadraticForm to bytes.
    """
    return x.to_bytes()


def deserialize(data: bytes, D: int) -> QuadraticForm:
    """
    Deserialize bytes into a QuadraticForm of discriminant D.
    """
    return QuadraticForm.from_bytes(data, D)

# --- Public VDF API -----------------------------------------------------

def generate(
    old_output: bytes,
    T: int,
    D: int
) -> Tuple[bytes, bytes]:
    """
    Evaluate the VDF by sequentially squaring the previous output 'T' times,
    then produce a Wesolowski proof.

    Returns:
      new_output : serialized new VDF output (y)
      proof      : serialized proof (π)
    """
    # Decode previous output
    x0 = deserialize(old_output, D)
    # Sequential squarings
    x = x0
    for _ in range(T):
        x = class_group_square(x)
    # Serialize output
    y_bytes = serialize(x)
    # Compute proof
    pi = compute_wesolowski_proof(x0, x, T)
    proof_bytes = serialize(pi)
    return y_bytes, proof_bytes


def verify(
    old_output: bytes,
    new_output: bytes,
    proof: bytes,
    T: int,
    D: int
) -> bool:
    """
    Verify the Wesolowski VDF proof.

    Returns True if valid, False otherwise.
    """
    x0 = deserialize(old_output, D)
    y  = deserialize(new_output, D)
    pi = deserialize(proof, D)
    return verify_wesolowski_proof(x0, y, pi, T)
