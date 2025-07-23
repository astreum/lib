from enum import IntEnum

class ObjectRequestType(IntEnum):
    OBJECT_GET = 0
    OBJECT_PUT = 1

class ObjectRequest:
    type: ObjectRequestType
    data: bytes
    hash: bytes

    def __init__(self, type: ObjectRequestType, data: bytes, hash: bytes = None):
        self.type = type
        self.data = data
        self.hash = hash

    def to_bytes(self):
        return [self.type.value] + self.hash + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectRequest":
        # need at least 1 byte for type + 32 bytes for hash
        if len(data) < 1 + 32:
            raise ValueError(f"Too short for ObjectRequest ({len(data)} bytes)")

        type_val = data[0]
        try:
            req_type = ObjectRequestType(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectRequestType: {type_val!r}")

        hash_bytes = data[1:33]
        payload    = data[33:]
        return cls(req_type, payload, hash_bytes)

class ObjectResponseType(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_NEAREST_PEER = 2

class ObjectResponse:
    type: ObjectResponseType
    data: bytes
    hash: bytes

    def __init__(self, type: ObjectResponseType, data: bytes, hash: bytes = None):
        self.type = type
        self.data = data
        self.hash = hash

    def to_bytes(self):
        return [self.type.value] + self.hash + self.data

    @classmethod
    def from_bytes(cls, data: bytes) -> "ObjectResponse":
        # need at least 1 byte for type + 32 bytes for hash
        if len(data) < 1 + 32:
            raise ValueError(f"Too short to be a valid ObjectResponse ({len(data)} bytes)")

        type_val = data[0]
        try:
            resp_type = ObjectResponseType(type_val)
        except ValueError:
            raise ValueError(f"Unknown ObjectResponseType: {type_val}")

        hash_bytes = data[1:33]
        payload   = data[33:]
        return cls(resp_type, payload, hash_bytes)
