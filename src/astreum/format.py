def encode(iterable, encoder=lambda x: x):
    """
    Encode an iterable of items into a single bytes object, applying the
    provided encoder function to each item to convert it into bytes.
    
    For each item (after applying encoder), we:
      - Determine its length (n)
      - Write a single byte to indicate how many bytes were used for the length:
          0: n == 0
          1: n <= 255
          2: 256 <= n <= 65535
          4: 65536 <= n <= 4294967295
          8: n > 4294967295
      - Write the little-endian encoding of n in the specified number of bytes (if n > 0)
      - Append the item’s data
    """
    result = bytearray()
    for item in iterable:
        item_bytes = encoder(item)
        n = len(item_bytes)
        if n > 4294967295:
            result.append(8)
            result.extend(n.to_bytes(8, byteorder='little'))
        elif n > 65535:
            result.append(4)
            result.extend(n.to_bytes(4, byteorder='little'))
        elif n > 255:
            result.append(2)
            result.extend(n.to_bytes(2, byteorder='little'))
        elif n > 0:
            result.append(1)
            result.extend(n.to_bytes(1, byteorder='little'))
        else:
            result.append(0)
        result.extend(item_bytes)
    return bytes(result)


def decode(buffer, decoder=lambda x: x):
    """
    Decode a bytes buffer into a list of items, applying the provided decoder
    function to convert the bytes into the desired type.
    
    The buffer is read sequentially:
      - Read one byte that indicates how many bytes were used for the length.
      - If this value is 0, then the item is empty.
      - Otherwise, read that many bytes to get the item's length (as a little-endian integer).
      - Then, slice the next 'length' bytes from the buffer to get the item data.
      - Apply the decoder function to the item data before appending it.
    
    By default, the decoder is the identity function, so items are returned as bytes.
    """
    decoded_data = []
    offset = 0
    buf_len = len(buffer)
    
    while offset < buf_len:
        length_type = buffer[offset]
        offset += 1

        if length_type == 0:
            n = 0
        else:
            if offset + length_type > buf_len:
                raise ValueError("Buffer too short for length field")
            n = int.from_bytes(buffer[offset: offset+length_type], byteorder='little')
            offset += length_type
        
        if offset + n > buf_len:
            raise ValueError("Buffer is too short for item data")
        item_data = buffer[offset:offset+n]
        offset += n
        decoded_data.append(decoder(item_data))
        
    return decoded_data