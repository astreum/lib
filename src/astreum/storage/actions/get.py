from __future__ import annotations

from time import sleep
from typing import List, Optional, Union

from ..models.atom import Atom, ZERO32
from ..providers import provider_payload_for_id
from ..cold.get import get_atom_from_cold_storage


def _hot_storage_get(self, key: bytes) -> Optional[Atom]:
    """Retrieve an atom from in-memory cache."""
    with self.hot_storage_lock:
        atom = self.hot_storage.get(key)
        if atom is not None:
            self.logger.debug("Hot storage hit for %s", key.hex())
        else:
            self.logger.debug("Hot storage miss for %s", key.hex())
        return atom


def _network_get(self, atom_id: bytes, payload_type: int) -> Optional[Union[Atom, List[Atom]]]:
    """Attempt to fetch an atom from network peers when local storage misses."""
    from ...communication.handlers.object_response import (
        OBJECT_FOUND_ATOM_PAYLOAD,
        OBJECT_FOUND_LIST_PAYLOAD,
    )

    def _wait_for_atom(atom_id: bytes, interval: float, retries: int) -> Optional[Atom]:
        if interval <= 0 or retries <= 0:
            return self.get_atom_from_local_storage(atom_id=atom_id)
        for _ in range(retries):
            atom = self.get_atom_from_local_storage(atom_id=atom_id)
            if atom is not None:
                return atom
            sleep(interval)
        return self.get_atom_from_local_storage(atom_id=atom_id)

    def _wait_for_list(root_hash: bytes, interval: float, retries: int) -> Optional[List[Atom]]:
        if interval <= 0 or retries <= 0:
            return self.get_atom_list_from_local_storage(root_hash=root_hash)
        for _ in range(retries):
            atoms = self.get_atom_list_from_local_storage(root_hash=root_hash)
            if atoms is not None:
                return atoms
            sleep(interval)
        return self.get_atom_list_from_local_storage(root_hash=root_hash)

    def _wait_for_payload() -> Optional[Union[Atom, List[Atom]]]:
        wait_interval = self.config["atom_fetch_interval"]
        wait_retries = self.config["atom_fetch_retries"]
        if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
            return _wait_for_atom(atom_id, wait_interval, wait_retries)
        if payload_type == OBJECT_FOUND_LIST_PAYLOAD:
            return _wait_for_list(atom_id, wait_interval, wait_retries)
        self.logger.warning(
            "Unknown payload type %s for %s",
            payload_type,
            atom_id.hex(),
        )
        return None

    if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
        local_atom = self.get_atom_from_local_storage(atom_id=atom_id)
        if local_atom is not None:
            return local_atom
    elif payload_type == OBJECT_FOUND_LIST_PAYLOAD:
        local_atoms = self.get_atom_list_from_local_storage(root_hash=atom_id)
        if local_atoms is not None:
            return local_atoms
    else:
        self.logger.warning(
            "Unknown payload type %s for %s",
            payload_type,
            atom_id.hex(),
        )

    if not getattr(self, "is_connected", False):
        self.logger.debug("Network fetch skipped for %s; node not connected", atom_id.hex())
        return None
    self.logger.debug("Attempting network fetch for %s", atom_id.hex())
    
    provider_id = self.storage_index.get(atom_id)
    if provider_id is not None:
        provider_payload = provider_payload_for_id(self, provider_id)
        if provider_payload is not None:
            try:
                from ...communication.handlers.object_response import decode_object_provider
                from ...communication.handlers.object_request import (
                    ObjectRequest,
                    ObjectRequestType,
                )
                from ...communication.models.message import Message, MessageTopic
                from ...communication.outgoing_queue import enqueue_outgoing
                from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey

                provider_key, provider_address, provider_port = decode_object_provider(provider_payload)
                provider_public_key = X25519PublicKey.from_public_bytes(provider_key)
                shared_key_bytes = self.relay_secret_key.exchange(provider_public_key)

                obj_req = ObjectRequest(
                    type=ObjectRequestType.OBJECT_GET,
                    data=b"",
                    atom_id=atom_id,
                    payload_type=payload_type,
                )
                message = Message(
                    topic=MessageTopic.OBJECT_REQUEST,
                    content=obj_req.to_bytes(),
                    sender=self.relay_public_key,
                )
                message.encrypt(shared_key_bytes)
                self.add_atom_req(atom_id, payload_type)
                queued = enqueue_outgoing(
                    self,
                    (provider_address, provider_port),
                    message=message,
                    difficulty=1,
                )
                if queued:
                    self.logger.debug(
                        "Requested atom %s from indexed provider %s:%s",
                        atom_id.hex(),
                        provider_address,
                        provider_port,
                    )
                else:
                    self.logger.debug(
                        "Dropped request for atom %s to indexed provider %s:%s",
                        atom_id.hex(),
                        provider_address,
                        provider_port,
                    )
            except Exception as exc:
                self.logger.warning("Failed indexed fetch for %s: %s", atom_id.hex(), exc)
            return _wait_for_payload()
        self.logger.warning("Unknown provider id %s for %s", provider_id, atom_id.hex())

    self.logger.debug("Falling back to network fetch for %s", atom_id.hex())

    from ...communication.handlers.object_request import (
        ObjectRequest,
        ObjectRequestType,
    )
    from ...communication.models.message import Message, MessageTopic
    from ...communication.outgoing_queue import enqueue_outgoing

    try:
        closest_peer = self.peer_route.closest_peer_for_hash(atom_id)
    except Exception as exc:
        self.logger.warning("Peer lookup failed for %s: %s", atom_id.hex(), exc)
        return _wait_for_payload()

    if closest_peer is None or closest_peer.address is None:
        self.logger.debug("No peer available to fetch %s", atom_id.hex())
        return None

    obj_req = ObjectRequest(
        type=ObjectRequestType.OBJECT_GET,
        data=b"",
        atom_id=atom_id,
        payload_type=payload_type,
    )
    try:
        message = Message(
            topic=MessageTopic.OBJECT_REQUEST,
            content=obj_req.to_bytes(),
            sender=self.relay_public_key,
        )
    except Exception as exc:
        self.logger.warning("Failed to build object request for %s: %s", atom_id.hex(), exc)
        return None

    # encrypt the outbound request for the target peer
    message.encrypt(closest_peer.shared_key_bytes)

    try:
        self.add_atom_req(atom_id, payload_type)
    except Exception as exc:
        self.logger.warning("Failed to track object request for %s: %s", atom_id.hex(), exc)

    try:
        queued = enqueue_outgoing(
            self,
            closest_peer.address,
            message=message,
            difficulty=closest_peer.difficulty,
        )
        if queued:
            self.logger.debug(
                "Queued OBJECT_GET for %s to peer %s",
                atom_id.hex(),
                closest_peer.address,
            )
        else:
            self.logger.debug(
                "Dropped OBJECT_GET for %s to peer %s",
                atom_id.hex(),
                closest_peer.address,
            )
    except Exception as exc:
        self.logger.warning(
            "Failed to queue OBJECT_GET for %s to %s: %s",
            atom_id.hex(),
            closest_peer.address,
            exc,
        )
    return _wait_for_payload()

def get_atom_from_local_storage(self, atom_id: bytes) -> Optional[Atom]:
    """Retrieve an Atom by checking only local hot and cold storage."""
    self.logger.debug("Fetching atom %s (local only)", atom_id.hex())
    atom = self._hot_storage_get(atom_id)
    if atom is not None:
        self.logger.debug("Returning atom %s from hot storage", atom_id.hex())
        return atom
    atom = get_atom_from_cold_storage(self, atom_id)
    if atom is not None:
        self.logger.debug("Returning atom %s from cold storage", atom_id.hex())
        return atom
    self.logger.debug("Local storage miss for %s", atom_id.hex())
    return None


def get_atom(self, atom_id: bytes) -> Optional[Atom]:
    """Retrieve an atom locally first, then request it from the network."""
    atom = self.get_atom_from_local_storage(atom_id=atom_id)
    if atom is not None:
        return atom
    from ...communication.handlers.object_response import OBJECT_FOUND_ATOM_PAYLOAD

    self.logger.debug(
        "Local atom miss for %s; requesting from network",
        atom_id.hex(),
    )
    result = self._network_get(atom_id, OBJECT_FOUND_ATOM_PAYLOAD)
    if isinstance(result, Atom):
        return result
    self.logger.debug(
        "Network fetch returned no atom for %s",
        atom_id.hex(),
    )
    return None


def get_atom_list_from_local_storage(self, root_hash: bytes) -> Optional[List[Atom]]:
    """Follow a local-only atom list chain, returning atoms or None on gaps."""
    next_id = root_hash
    atoms: List[Atom] = []
    while next_id != ZERO32:
        atom = self.get_atom_from_local_storage(atom_id=next_id)
        if atom is None:
            return None
        atoms.append(atom)
        next_id = atom.next_id
    return atoms


def get_atom_list(self, root_hash: bytes) -> Optional[List[Atom]]:
    """Retrieve an atom list locally first, then request it from the network."""
    atoms = self.get_atom_list_from_local_storage(root_hash=root_hash)
    if atoms is not None:
        return atoms
    from ...communication.handlers.object_response import OBJECT_FOUND_LIST_PAYLOAD

    self.logger.debug(
        "Local list miss for %s; requesting from network",
        root_hash.hex(),
    )
    result = self._network_get(root_hash, OBJECT_FOUND_LIST_PAYLOAD)
    if isinstance(result, list):
        return result
    self.logger.debug(
        "Network fetch returned no list for %s",
        root_hash.hex(),
    )
    return None
