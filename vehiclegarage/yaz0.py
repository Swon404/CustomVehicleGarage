"""Yaz0 compression as used by .szs archives."""

import struct
from collections.abc import Callable

MAGIC = b"Yaz0"
_MAX_MATCH = 0x111
_WINDOW = 0x1000
_MAX_CHAIN = 24


def is_yaz0(data: bytes) -> bool:
    return data[:4] == MAGIC


def decompress(data: bytes) -> bytes:
    if not is_yaz0(data):
        raise ValueError("not a Yaz0 stream")
    (size,) = struct.unpack_from(">I", data, 4)
    out = bytearray()
    src = 16
    while len(out) < size:
        flags = data[src]
        src += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                out.append(data[src])
                src += 1
                continue
            b1, b2 = data[src], data[src + 1]
            src += 2
            distance = ((b1 & 0x0F) << 8 | b2) + 1
            length = b1 >> 4
            if length == 0:
                length = data[src] + 0x12
                src += 1
            else:
                length += 2
            start = len(out) - distance
            if start < 0:
                raise ValueError("corrupt Yaz0 stream")
            if distance >= length:
                out += out[start : start + length]
            else:
                for i in range(length):
                    out.append(out[start + i])
    return bytes(out[:size])


def compress(data: bytes, progress: Callable[[float], None] | None = None) -> bytes:
    """Greedy hash-chain Yaz0 encoder; output is valid for the game and decodes to `data`."""
    size = len(data)
    out = bytearray(MAGIC + struct.pack(">I", size) + bytes(8))
    heads: dict[bytes, list[int]] = {}
    pos = 0
    group = bytearray()
    flags = 0
    count = 0
    next_report = 0

    def insert(p: int) -> None:
        if p + 3 <= size:
            chain = heads.setdefault(data[p : p + 3], [])
            chain.append(p)
            if len(chain) > _MAX_CHAIN * 2:
                del chain[: len(chain) - _MAX_CHAIN]

    while pos < size:
        best_len = 0
        best_dist = 0
        if pos + 3 <= size:
            chain = heads.get(data[pos : pos + 3])
            if chain:
                limit = min(_MAX_MATCH, size - pos)
                low = pos - _WINDOW
                for cand in reversed(chain[-_MAX_CHAIN:]):
                    if cand < low:
                        break
                    length = 3
                    while length < limit and data[cand + length] == data[pos + length]:
                        length += 1
                    if length > best_len:
                        best_len = length
                        best_dist = pos - cand
                        if length == limit:
                            break
        if best_len >= 3:
            d = best_dist - 1
            if best_len < 0x12:
                group += bytes(((best_len - 2) << 4 | d >> 8, d & 0xFF))
            else:
                group += bytes((d >> 8, d & 0xFF, best_len - 0x12))
            for p in range(pos, pos + best_len):
                insert(p)
            pos += best_len
        else:
            flags |= 0x80 >> count
            group.append(data[pos])
            insert(pos)
            pos += 1
        count += 1
        if count == 8:
            out.append(flags)
            out += group
            group.clear()
            flags = 0
            count = 0
            if progress and pos >= next_report:
                progress(pos / size)
                next_report = pos + 65536
    if count:
        out.append(flags)
        out += group
    if progress:
        progress(1.0)
    return bytes(out)
