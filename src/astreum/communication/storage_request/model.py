from astreum.communication.storage_request.code import StorageRequestCode


class StorageRequest:
    code: StorageRequestCode
    data: bytes
    expr_id: bytes
    payload_type: int | None

    def __init__(
        self,
        code: StorageRequestCode,
        data: bytes = b"",
        expr_id: bytes = None,
        payload_type: int | None = None,
    ):
        self.code = code
        self.data = data
        self.expr_id = expr_id
        self.payload_type = payload_type

    def to_bytes(self):
        if self.code == StorageRequestCode.STORAGE_PUT and self.payload_type is None:
            raise ValueError("STORAGE_PUT requires payload_type")
        if self.payload_type is not None:
            payload = bytes([self.payload_type]) + self.data
        else:
            payload = self.data
        return bytes([self.code.value]) + self.expr_id + payload

    @classmethod
    def from_bytes(cls, data: bytes) -> "StorageRequest":
        # need at least 1 byte for type + 32 bytes for hash
        if len(data) < 1 + 32:
            raise ValueError(f"Too short for StorageRequest ({len(data)} bytes)")

        type_val = data[0]
        try:
            req_type = StorageRequestCode(type_val)
        except ValueError:
            raise ValueError(f"Unknown StorageRequestCode: {type_val!r}")

        expr_id_bytes = data[1:33]
        payload = data[33:]
        if req_type == StorageRequestCode.STORAGE_GET:
            if payload:
                payload_type = payload[0]
                payload = payload[1:]
            else:
                payload_type = None
            return cls(req_type, payload, expr_id_bytes, payload_type=payload_type)
        if req_type == StorageRequestCode.STORAGE_PUT:
            if not payload:
                raise ValueError("STORAGE_PUT missing payload type")
            payload_type = payload[0]
            payload = payload[1:]
            return cls(req_type, payload, expr_id_bytes, payload_type=payload_type)
        return cls(req_type, payload, expr_id_bytes)
