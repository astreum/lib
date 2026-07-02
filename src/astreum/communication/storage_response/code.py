from enum import IntEnum


class StorageResponseCode(IntEnum):
    STORAGE_FOUND = 0
    STORAGE_PROVIDER = 1
    STORAGE_PAYMENT_REQUIRED = 2
