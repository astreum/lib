

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
        return encode([self.type.value, self.data, self.hash])

    @classmethod
    def from_bytes(cls, data: bytes):
        type_val, data_val, hash_val = decode(data)
        return cls(type=ObjectRequestType(type_val[0]), data=data_val, hash=hash_val)

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
        return encode([self.type.value, self.data, self.hash])

    @classmethod
    def from_bytes(cls, data: bytes):
        type_val, data_val, hash_val = decode(data)
        return cls(type=ObjectResponseType(type_val[0]), data=data_val, hash=hash_val)