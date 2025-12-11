from enum import IntEnum


class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2


class ObjectResponse:
    type: ObjectResponseType
    data: bytes
    atom_id: bytes

    def __init__(self, type: ObjectResponseType, data: bytes, atom_id: bytes = None):
        self.type = type
        self.data = data
        self.atom_id = atom_id

    def to_bytes(self):
        return [self.type.value] + self.atom_id + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectResponse":
        # need at least 1 byte for type + 32 bytes for atom id
        if len(data) < 1 + 32:
            raise ValueError(f"Too short to be a valid ObjectResponse ({len(data)} bytes)")

        type_val = data[0]
        try:
            resp_type = ObjectResponseType(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectResponseType: {type_val}")

        atom_id = data[1:33]
        payload   = data[33:]
        return cls(resp_type, payload, atom_id)
