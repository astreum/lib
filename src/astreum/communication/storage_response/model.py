from astreum.communication.storage_response.code import StorageResponseCode


class StorageResponse:
    code: StorageResponseCode
    data: bytes
    expr_id: bytes

    def __init__(self, code: StorageResponseCode, data: bytes, expr_id: bytes = None):
        self.code = code
        self.data = data
        self.expr_id = expr_id

    def to_bytes(self):
        return bytes([self.code.value]) + self.expr_id + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "StorageResponse":
        # need at least 1 byte for type + 32 bytes for expr id
        if len(data) < 1 + 32:
            raise ValueError(f"Too short to be a valid StorageResponse ({len(data)} bytes)")

        type_val = data[0]
        try:
            resp_type = StorageResponseCode(type_val)
        except ValueError:
            raise ValueError(f"Unknown StorageResponseCode: {type_val}")

        expr_id = data[1:33]
        payload = data[33:]
        return cls(resp_type, payload, expr_id)
