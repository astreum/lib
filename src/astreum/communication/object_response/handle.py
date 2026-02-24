from typing import TYPE_CHECKING

from ..models.message import Message
from ..models.peer import increment_peer_metric
from ..object_response.object_found import (
    OBJECT_FOUND_ATOM_PAYLOAD,
    OBJECT_FOUND_LIST_PAYLOAD,
    decode_object_found_list_payload,
)
from ..object_response.code import ObjectResponseCode
from ..object_response.model import ObjectResponse
from ..object_response.object_payment_required import decode_object_payment_required
from ..object_response.object_provider import decode_object_provider
from ..object_response.retry import _retry_pending_object_get_via_peer_contact
from ...storage.models.atom import Atom

if TYPE_CHECKING:
    from .. import Node
    from ..models.peer import Peer

def handle_object_response(node: "Node", peer: "Peer", message: Message) -> None:
    if message.content is None:
        node.logger.warning("OBJECT_RESPONSE from %s missing content", peer.address)
        return

    try:
        object_response = ObjectResponse.from_bytes(message.content)
    except Exception as exc:
        node.logger.warning("Error decoding OBJECT_RESPONSE from %s: %s", peer.address, exc)
        return

    if not node.has_atom_req(object_response.atom_id):
        return

    match object_response.code:
        case ObjectResponseCode.OBJECT_FOUND:
            payload = object_response.data
            if not payload:
                node.logger.warning(
                    "OBJECT_FOUND payload for %s missing content",
                    object_response.atom_id.hex(),
                )
                return

            payload_type = payload[0]
            body = payload[1:]

            if payload_type == OBJECT_FOUND_ATOM_PAYLOAD:
                try:
                    atom = Atom.from_bytes(body)
                except Exception as exc:
                    node.logger.warning(
                        "Invalid OBJECT_FOUND atom payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return

                atom_id = atom.object_id()
                if object_response.atom_id != atom_id:
                    node.logger.warning(
                        "OBJECT_FOUND atom ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        atom_id.hex(),
                    )
                    return

                node.pop_atom_req(atom_id)
                increment_peer_metric(peer, "shared_storage_download", len(body))
                node._hot_storage_set(atom_id, atom)
                return

            if payload_type == OBJECT_FOUND_LIST_PAYLOAD:
                try:
                    atoms = decode_object_found_list_payload(body)
                except Exception as exc:
                    node.logger.warning(
                        "Invalid OBJECT_FOUND list payload for %s: %s",
                        object_response.atom_id.hex(),
                        exc,
                    )
                    return

                if not atoms:
                    node.logger.warning(
                        "OBJECT_FOUND list payload for %s contained no atoms",
                        object_response.atom_id.hex(),
                    )
                    return

                node.logger.debug(
                    "OBJECT_FOUND list response atom_id=%s atoms=%s",
                    object_response.atom_id.hex(),
                    len(atoms),
                )
                root_id = atoms[0].object_id()
                if object_response.atom_id != root_id:
                    node.logger.warning(
                        "OBJECT_FOUND list root ID mismatch (expected=%s got=%s)",
                        object_response.atom_id.hex(),
                        root_id.hex(),
                    )
                    return

                node.pop_atom_req(root_id)
                increment_peer_metric(
                    peer,
                    "shared_storage_download",
                    sum(len(atom.to_bytes()) for atom in atoms),
                )
                for atom in atoms:
                    node._hot_storage_set(atom.object_id(), atom)
                return

            node.logger.warning(
                "Unknown OBJECT_FOUND payload type %s for %s",
                payload_type,
                object_response.atom_id.hex(),
            )

        case ObjectResponseCode.OBJECT_PROVIDER:
            try:
                provider_key_bytes, provider_address, provider_port = decode_object_provider(
                    object_response.data
                )
            except Exception as exc:
                node.logger.warning("Invalid OBJECT_PROVIDER payload from %s: %s", peer.address, exc)
                return

            _retry_pending_object_get_via_peer_contact(
                node,
                atom_id=object_response.atom_id,
                peer_contact=(provider_key_bytes, provider_address, provider_port),
            )

        case ObjectResponseCode.OBJECT_PAYMENT_REQUIRED:
            try:
                payment_public_key, storage_size_estimate, base_storage_fee, hint_peer = (
                    decode_object_payment_required(object_response.data)
                )
            except Exception as exc:
                node.logger.warning(
                    "Invalid OBJECT_PAYMENT_REQUIRED payload from %s: %s",
                    peer.address,
                    exc,
                )
                return
            node.logger.debug(
                "Received OBJECT_PAYMENT_REQUIRED from %s (payment_key=%s, size_estimate=%s, base_storage_fee=%s, hint=%s)",
                peer.address,
                payment_public_key.hex(),
                storage_size_estimate,
                base_storage_fee,
                hint_peer,
            )

            has_local_payment_key = bool(
                getattr(node, "relay_payment_secret_key", None)
                or (getattr(node, "config", {}) or {}).get("relay_payment_secret_key")
            )
            if has_local_payment_key:
                return

            if hint_peer is not None:
                node.logger.info(
                    "OBJECT_PAYMENT_REQUIRED for %s from %s but no local payment key; trying hint %s:%s",
                    object_response.atom_id.hex(),
                    peer.address,
                    hint_peer[1],
                    hint_peer[2],
                )
                if _retry_pending_object_get_via_peer_contact(
                    node,
                    atom_id=object_response.atom_id,
                    peer_contact=hint_peer,
                ):
                    return
                node.logger.info(
                    "Hint retry failed for %s after OBJECT_PAYMENT_REQUIRED from %s; ending request",
                    object_response.atom_id.hex(),
                    peer.address,
                )

            else:
                node.logger.info(
                    "OBJECT_PAYMENT_REQUIRED for %s from %s and no local payment key or hint; ending request",
                    object_response.atom_id.hex(),
                    peer.address,
                )

            node.pop_atom_req(object_response.atom_id)
            return
