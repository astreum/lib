"""Core Astreum Node implementation."""

from __future__ import annotations

from astreum.communication.node import connect_node
from astreum.communication.util import get_bootstrap_peers
from astreum.communication.disconnect import disconnect_node
from astreum.communication.models.peer import (
    add_peer as peers_add_peer,
    replace_peer as peers_replace_peer,
    get_peer as peers_get_peer,
    remove_peer as peers_remove_peer,
)
from astreum.validation.node import validate_blockchain
from astreum.consensus.verification.node import verify_blockchain
from astreum.storage.actions.set import (
    add_expr_advertisement,
    add_expr_advertisements,
)
from astreum.storage.requests import add_expr_req, has_expr_req, pop_expr_req
from astreum.storage.setup import setup_storage
from astreum.utils.config import config_setup
from astreum.utils.logging import logging_setup


class Node:
    def __init__(self, config: dict = {}):
        self.config = config_setup(config=config)
        self.bootstrap_peers = get_bootstrap_peers(self)
        
        self.logger = logging_setup(self.config)

        self.logger.info("Starting Astreum Node")

        # Chain Configuration
        self.logger.info(f"Chain configured as: {self.config['chain']} ({self.config['chain_id']})")

        # Storage Setup
        setup_storage(self, config=self.config)

        # Machine Setup
        self.is_connected = False
        self.latest_block_hash = None
        self.latest_block = None
        
    connect = connect_node
    disconnect = disconnect_node

    verify = verify_blockchain
    validate = validate_blockchain

    ## Set
    add_expr_advertisement = add_expr_advertisement
    add_expr_advertisements = add_expr_advertisements

    add_expr_req = add_expr_req
    has_expr_req = has_expr_req
    pop_expr_req = pop_expr_req

    add_peer = peers_add_peer
    replace_peer = peers_replace_peer
    get_peer = peers_get_peer
    remove_peer = peers_remove_peer
