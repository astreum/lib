def connect_to_network_and_verify(self):
    """Initialize communication and consensus components, then load latest block state."""
    node_logger = self.logger
    node_logger.info("Starting communication and consensus setup")
    try:
        from astreum.communication import communication_setup  # type: ignore
        communication_setup(node=self, config=self.config)
        node_logger.info("Communication setup completed")
    except Exception:
        node_logger.exception("Communication setup failed")

    try:
        from astreum.consensus import consensus_setup  # type: ignore
        consensus_setup(node=self, config=self.config)
        node_logger.info("Consensus setup completed")
    except Exception:
        node_logger.exception("Consensus setup failed")

    # Load latest_block_hash from config
    self.latest_block_hash = getattr(self, "latest_block_hash", None)
    self.latest_block = getattr(self, "latest_block", None)

    latest_block_hex = self.config.get("latest_block_hash")
    if latest_block_hex and self.latest_block_hash is None:
        try:
            from astreum.utils.bytes import hex_to_bytes
            self.latest_block_hash = hex_to_bytes(latest_block_hex, expected_length=32)
            node_logger.debug("Loaded latest_block_hash override from config")
        except Exception as exc:
            node_logger.error("Invalid latest_block_hash in config: %s", exc)

    if self.latest_block_hash and self.latest_block is None:
        try:
            from astreum.consensus.models.block import Block
            self.latest_block = Block.from_atom(self, self.latest_block_hash)
            node_logger.info("Loaded latest block %s from storage", self.latest_block_hash.hex())
        except Exception as exc:
            node_logger.warning("Could not load latest block from storage: %s", exc)
