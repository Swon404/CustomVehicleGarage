"""Read and replace vehicle-name messages in Mario Kart Wii BMG files."""

import struct
from collections.abc import Mapping

VEHICLE_COUNT = 36
HEADER_SIZE = 0x20
def valid_vehicle_name(name: str) -> bool:
    if not name or any(ord(char) < 0x20 for char in name):
        return False
    try:
        name.encode("utf-16-be")
    except UnicodeEncodeError:
        return False
    return True


def vehicle_name_message_ids(slot: int) -> tuple[int, ...]:
    if not 0 <= slot < VEHICLE_COUNT:
        raise ValueError(f"vehicle slot {slot} is outside 0..{VEHICLE_COUNT - 1}")
    if slot < 18:
        ids = [9100 + slot]
        if slot < 3:
            ids.extend((9118 + slot, 9121 + slot))
        return tuple(ids)
    bike = slot - 18
    ids = [9150 + bike]
    if bike < 3:
        ids.extend((9168 + bike, 9171 + bike))
    return tuple(ids)


def _layout(data: bytes):
    if len(data) < HEADER_SIZE or data[:8] != b"MESGbmg1":
        raise ValueError("invalid BMG header")
    file_size, section_count = struct.unpack_from(">II", data, 8)
    if file_size != len(data) or data[0x10] != 2:
        raise ValueError("unsupported BMG size or encoding")

    sections = {}
    offset = HEADER_SIZE
    for _ in range(section_count):
        if offset + 8 > file_size:
            raise ValueError("truncated BMG section header")
        kind = data[offset : offset + 4]
        size = struct.unpack_from(">I", data, offset + 4)[0]
        if size < 8 or offset + size > file_size or kind in sections:
            raise ValueError("invalid BMG section")
        sections[kind] = (offset, size)
        offset += size
    if offset != file_size or not all(kind in sections for kind in (b"INF1", b"DAT1", b"MID1")):
        raise ValueError("BMG is missing required sections")

    info_offset, info_size = sections[b"INF1"]
    count, entry_size = struct.unpack_from(">HH", data, info_offset + 8)
    if entry_size != 8 or 16 + count * entry_size > info_size:
        raise ValueError("unsupported BMG message index")

    ids_offset, ids_size = sections[b"MID1"]
    id_count = struct.unpack_from(">H", data, ids_offset + 8)[0]
    if id_count != count or 16 + id_count * 4 > ids_size:
        raise ValueError("BMG message ID table does not match its index")

    offsets_by_id = {}
    pool_offsets = set()
    for index in range(count):
        pool_offset = struct.unpack_from(">I", data, info_offset + 16 + index * entry_size)[0]
        message_id = struct.unpack_from(">I", data, ids_offset + 16 + index * 4)[0]
        if message_id in offsets_by_id:
            raise ValueError(f"duplicate BMG message ID {message_id}")
        offsets_by_id[message_id] = pool_offset
        pool_offsets.add(pool_offset)

    pool_offset, pool_section_size = sections[b"DAT1"]
    pool_start = pool_offset + 8
    pool_size = pool_section_size - 8
    if any(offset < 0 or offset + 2 > pool_size for offset in pool_offsets):
        raise ValueError("BMG message points outside its string pool")
    return offsets_by_id, sorted(pool_offsets), pool_start, pool_size


def read_message(data: bytes, message_id: int) -> str:
    offsets_by_id, _pool_offsets, pool_start, pool_size = _layout(data)
    if message_id not in offsets_by_id:
        raise KeyError(message_id)
    start = pool_start + offsets_by_id[message_id]
    end = start
    pool_end = pool_start + pool_size
    while end + 1 < pool_end and data[end : end + 2] != b"\0\0":
        end += 2
    if end + 1 >= pool_end:
        raise ValueError(f"BMG message {message_id} has no terminator")
    try:
        return data[start:end].decode("utf-16-be")
    except UnicodeDecodeError as err:
        raise ValueError(f"BMG message {message_id} is not valid UTF-16BE") from err


def vehicle_name_capacities(data: bytes) -> list[int]:
    offsets_by_id, pool_offsets, _pool_start, pool_size = _layout(data)
    limits = {
        offset: pool_offsets[index + 1] if index + 1 < len(pool_offsets) else pool_size
        for index, offset in enumerate(pool_offsets)
    }
    capacities = []
    for slot in range(VEHICLE_COUNT):
        sizes = []
        for message_id in vehicle_name_message_ids(slot):
            if message_id not in offsets_by_id:
                raise ValueError(f"BMG does not contain vehicle-name message {message_id}")
            offset = offsets_by_id[message_id]
            sizes.append(max(0, (limits[offset] - offset) // 2 - 1))
        capacities.append(min(sizes))
    return capacities


def replace_messages(data: bytes, replacements: Mapping[int, str]) -> bytes:
    """Replace message text by ID without changing BMG file size."""
    offsets_by_id, pool_offsets, pool_start, pool_size = _layout(data)
    limits = {
        offset: pool_offsets[index + 1] if index + 1 < len(pool_offsets) else pool_size
        for index, offset in enumerate(pool_offsets)
    }
    writes: dict[int, bytes] = {}
    for message_id, replacement in replacements.items():
        if message_id not in offsets_by_id:
            raise ValueError(f"BMG does not contain vehicle-name message {message_id}")
        if not replacement or any(ord(char) < 0x20 for char in replacement):
            raise ValueError("vehicle names must contain printable characters")
        try:
            encoded = replacement.encode("utf-16-be")
        except UnicodeEncodeError as err:
            raise ValueError("vehicle name cannot be encoded as UTF-16") from err

        offset = offsets_by_id[message_id]
        start = pool_start + offset
        original = read_message(data, message_id).encode("utf-16-be")
        expected_end = start + len(original)
        if data[expected_end : expected_end + 2] != b"\0\0":
            raise ValueError(f"BMG message {message_id} is not a plain vehicle name")
        available = limits[offset] - offset
        if len(encoded) + 2 > available:
            max_chars = max(0, available // 2 - 1)
            raise ValueError(
                f"vehicle name is too long for this slot; this menu entry allows up to {max_chars} UTF-16 code units"
            )
        content = encoded + b"\0\0"
        previous = writes.get(offset)
        if previous is not None and previous != content:
            raise ValueError(f"conflicting replacement text for BMG string at offset {offset}")
        writes[offset] = content

    patched = bytearray(data)
    for offset, content in writes.items():
        start = pool_start + offset
        patched[start : start + len(content)] = content
    return bytes(patched)
