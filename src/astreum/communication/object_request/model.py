from typing import Optional

from .code import ObjectRequestCode


class ObjectRequest:
    code: ObjectRequestCode
    data: bytes
    atom_id: bytes
    payload_type: Optional[int]

    def __init__(
        self,
        code: ObjectRequestCode,
        data: bytes = b"",
        atom_id: bytes = None,
        payload_type: Optional[int] = None,
    ):
        self.code = code
        self.data = data
        self.atom_id = atom_id
        self.payload_type = payload_type

    def to_bytes(self):
        if self.code == ObjectRequestCode.OBJECT_PUT and self.payload_type is None:
            raise ValueError("OBJECT_PUT requires payload_type")
        if self.payload_type is not None:
            payload = bytes([self.payload_type]) + self.data
        else:
            payload = self.data
        return bytes([self.code.value]) + self.atom_id + payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectRequest":
        # need at least 1 byte for type + 32 bytes for hash
        if len(data) < 1 + 32:
            raise ValueError(f"Too short for ObjectRequest ({len(data)} bytes)")

        type_val = data[0]
        try:
            req_type = ObjectRequestCode(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectRequestCode: {type_val!r}")

        atom_id_bytes = data[1:33]
        payload = data[33:]
        if req_type == ObjectRequestCode.OBJECT_GET:
            if payload:
                payload_type = payload[0]
                payload = payload[1:]
            else:
                payload_type = None
            return cls(req_type, payload, atom_id_bytes, payload_type=payload_type)
        if req_type == ObjectRequestCode.OBJECT_PUT:
            if not payload:
                raise ValueError("OBJECT_PUT missing payload type")
            payload_type = payload[0]
            payload = payload[1:]
            return cls(req_type, payload, atom_id_bytes, payload_type=payload_type)
        return cls(req_type, payload, atom_id_bytes)
