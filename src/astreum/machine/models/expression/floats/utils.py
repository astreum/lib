from struct import Struct

_unpack_u16 = Struct('<H').unpack
_unpack_fp16 = Struct('<e').unpack
_unpack_fp32 = Struct('<f').unpack
