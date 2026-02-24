from enum import IntEnum


class ObjectResponseCode(IntEnum):
    OBJECT_FOUND = 0
    OBJECT_PROVIDER = 1
    OBJECT_PAYMENT_REQUIRED = 2
