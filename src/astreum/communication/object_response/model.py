from .code import ObjectResponseCode


class ObjectResponse:
    code: ObjectResponseCode
    data: bytes
    atom_id: bytes

    def __init__(self, code: ObjectResponseCode, data: bytes, atom_id: bytes = None):
        self.code = code
        self.data = data
        self.atom_id = atom_id

    def to_bytes(self):
        return bytes([self.code.value]) + self.atom_id + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectResponse":
        # need at least 1 byte for type + 32 bytes for atom id
        if len(data) < 1 + 32:
            raise ValueError(f"Too short to be a valid ObjectResponse ({len(data)} bytes)")

        type_val = data[0]
        try:
            resp_type = ObjectResponseCode(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectResponseCode: {type_val}")

        atom_id = data[1:33]
        payload = data[33:]
        return cls(resp_type, payload, atom_id)
