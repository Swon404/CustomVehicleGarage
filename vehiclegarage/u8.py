"""Locate and replace files inside U8 archives (the payload of .szs files)."""

import struct

MAGIC = b"\x55\xAA\x38\x2D"


def find_files(data: bytes) -> dict[str, tuple[int, int]]:
    """Map every file path in a U8 archive to its (offset, size)."""
    if data[:4] != MAGIC:
        raise ValueError("not a U8 archive")
    root_offset, _, _ = struct.unpack_from(">III", data, 4)
    node_count = struct.unpack_from(">I", data, root_offset + 8)[0]
    names_base = root_offset + node_count * 12

    def node(i: int) -> tuple[int, int, int, int]:
        kind_name, a, b = struct.unpack_from(">III", data, root_offset + i * 12)
        return kind_name >> 24, kind_name & 0xFFFFFF, a, b

    def name_of(offset: int) -> str:
        end = data.index(b"\0", names_base + offset)
        return data[names_base + offset : end].decode("utf-8")

    files: dict[str, tuple[int, int]] = {}
    dir_stack: list[tuple[str, int]] = [("", node_count)]
    for i in range(1, node_count):
        while len(dir_stack) > 1 and i >= dir_stack[-1][1]:
            dir_stack.pop()
        kind, name_off, a, b = node(i)
        name = name_of(name_off)
        prefix = dir_stack[-1][0]
        if kind == 1:
            dir_stack.append((f"{prefix}{name}/", b))
        else:
            files[f"{prefix}{name}"] = (a, b)
    # Nintendo archives nest everything under a "." directory.
    return {(p[2:] if p.startswith("./") else p): v for p, v in files.items()}


def replace_file(data: bytes, path: str, new_content: bytes) -> bytes:
    """Overwrite a file in place; the replacement must be exactly the same size."""
    files = find_files(data)
    if path not in files:
        raise KeyError(f"{path} is not in the archive")
    offset, size = files[path]
    if len(new_content) != size:
        raise ValueError(f"{path} must stay {size} bytes, got {len(new_content)}")
    return data[:offset] + new_content + data[offset + size :]


def read_file(data: bytes, path: str) -> bytes:
    files = find_files(data)
    if path not in files:
        raise KeyError(f"{path} is not in the archive")
    offset, size = files[path]
    return data[offset : offset + size]
