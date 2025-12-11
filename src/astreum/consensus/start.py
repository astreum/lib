from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from astreum.consensus.genesis import create_genesis_block


def process_blocks_and_transactions(self, validator_secret_key: Ed25519PrivateKey):
    """Initialize validator keys, ensure genesis exists, then start validation thread."""
    self.logger.info(
        "Initializing block and transaction processing for chain %s",
        self.config["chain"],
    )

    self.validation_secret_key = validator_secret_key
    validator_public_key_obj = self.validation_secret_key.public_key()
    validator_public_key_bytes = validator_public_key_obj.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    self.validation_public_key = validator_public_key_bytes
    self.logger.debug(
        "Derived validator public key %s", validator_public_key_bytes.hex()
    )

    if self.latest_block_hash is None:
        genesis_block = create_genesis_block(
            self,
            validator_public_key=validator_public_key_bytes,
            chain_id=self.config["chain_id"],
        )
        account_atoms = genesis_block.accounts.update_trie(self) if genesis_block.accounts else []

        genesis_hash, genesis_atoms = genesis_block.to_atom()
        self.logger.debug(
            "Genesis block created with %s atoms (%s account atoms)",
            len(genesis_atoms),
            len(account_atoms),
        )

        for atom in account_atoms + genesis_atoms:
            try:
                self._hot_storage_set(key=atom.object_id(), value=atom)
            except Exception as exc:
                self.logger.warning(
                    "Unable to persist genesis atom %s: %s",
                    atom.object_id(),
                    exc,
                )

        self.latest_block_hash = genesis_hash
        self.latest_block = genesis_block
        self.logger.info("Genesis block stored with hash %s", genesis_hash.hex())
    else:
        self.logger.debug(
            "latest_block_hash already set to %s; skipping genesis creation",
            self.latest_block_hash.hex()
            if isinstance(self.latest_block_hash, (bytes, bytearray))
            else self.latest_block_hash,
        )

    self.logger.info(
        "Starting consensus validation thread (%s)",
        self.consensus_validation_thread.name,
    )
    self.consensus_validation_thread.start()

    # ping all peers to announce validation capability
