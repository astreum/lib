# Diffie-Hellman key exchange over Curve25519 test

from astreum.node.crypto.x25519 import generate_key_pair, generate_shared_key

def test_x25519_shared_key_equality():
    """
    Tests that the shared key generation is commutative.
    
    Generates two key pairs (Alice and Bob) and verifies that the shared key
    derived by Alice using Bob's public key is the same as the shared key
    derived by Bob using Alice's public key.
    """
    # Generate key pairs for Alice and Bob
    alice_private_key, alice_public_key = generate_key_pair()
    bob_private_key, bob_public_key = generate_key_pair()
    
    # Alice computes the shared key using Bob's public key
    shared_key_alice = generate_shared_key(alice_private_key, bob_public_key)
    
    # Bob computes the shared key using Alice's public key
    shared_key_bob = generate_shared_key(bob_private_key, alice_public_key)
    
    # Assert that the shared keys are equal
    assert shared_key_alice == shared_key_bob
    assert isinstance(shared_key_alice, bytes)
    assert len(shared_key_alice) == 32  # X25519 shared keys are 32 bytes

if __name__ == "__main__":
    try:
        test_x25519_shared_key_equality()
        print("X25519 shared key equality test passed!")
    except AssertionError:
        print("X25519 shared key equality test FAILED!")
        # Re-raise the assertion error to get the traceback if needed
        raise
