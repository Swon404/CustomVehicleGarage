import random
import struct
import unittest

from vehiclegarage import u8, yaz0


def build_u8(tree: dict) -> bytes:
    """Build a minimal U8 archive from a nested dict of {name: bytes | dict}."""
    nodes: list[tuple[int, int, int, int]] = []  # (kind, name_offset, a, b)
    names = bytearray(b"\0")
    blobs: list[bytes] = []

    def add_dir(children: dict, parent: int, name: str) -> None:
        index = len(nodes)
        name_offset = len(names)
        names.extend(name.encode() + b"\0")
        nodes.append([1, name_offset, parent, 0])
        for child_name, child in children.items():
            if isinstance(child, dict):
                add_dir(child, index, child_name)
            else:
                offset = len(names)
                names.extend(child_name.encode() + b"\0")
                nodes.append([0, offset, len(blobs), len(child)])
                blobs.append(child)
        nodes[index][3] = len(nodes)

    nodes.append([1, 0, 0, 0])
    for child_name, child in tree.items():
        if isinstance(child, dict):
            add_dir(child, 0, child_name)
        else:
            offset = len(names)
            names.extend(child_name.encode() + b"\0")
            nodes.append([0, offset, len(blobs), len(child)])
            blobs.append(child)
    nodes[0][3] = len(nodes)

    node_bytes_len = len(nodes) * 12 + len(names)
    data_start = (0x20 + node_bytes_len + 0x1F) & ~0x1F
    out = bytearray(data_start)
    cursor = data_start
    offsets = []
    for blob in blobs:
        offsets.append(cursor)
        out += blob
        cursor += len(blob)
        pad = (-cursor) % 0x20
        out += bytes(pad)
        cursor += pad
    table = bytearray()
    for kind, name_offset, a, b in nodes:
        if kind == 0:
            a = offsets[a]
        table += struct.pack(">III", kind << 24 | name_offset, a, b)
    out[0:0x20] = struct.pack(">4sIIII", u8.MAGIC, 0x20, node_bytes_len, data_start, 0).ljust(0x20, b"\0")
    out[0x20 : 0x20 + len(table)] = table
    out[0x20 + len(table) : 0x20 + len(table) + len(names)] = names
    return bytes(out)


class Yaz0Tests(unittest.TestCase):
    def test_round_trip_repetitive_and_random_data(self):
        rng = random.Random(1)
        data = b"abcabcabc" * 500 + bytes(rng.randrange(256) for _ in range(3000)) + b"\0" * 1000
        packed = yaz0.compress(data)
        self.assertTrue(yaz0.is_yaz0(packed))
        self.assertEqual(yaz0.decompress(packed), data)
        self.assertLess(len(packed), len(data))

    def test_round_trip_tiny_inputs(self):
        for data in (b"", b"a", b"ab", b"abc", b"aaaa"):
            self.assertEqual(yaz0.decompress(yaz0.compress(data)), data)


class U8Tests(unittest.TestCase):
    def setUp(self):
        self.archive = build_u8({".": {"kartParam.bin": b"A" * 40, "sub": {"x.bin": b"BB"}}, "other.txt": b"hello"})

    def test_finds_files_and_strips_leading_dot_directory(self):
        files = u8.find_files(self.archive)
        self.assertEqual(set(files), {"kartParam.bin", "sub/x.bin", "other.txt"})
        self.assertEqual(u8.read_file(self.archive, "sub/x.bin"), b"BB")

    def test_replace_changes_only_that_file(self):
        patched = u8.replace_file(self.archive, "kartParam.bin", b"Z" * 40)
        self.assertEqual(len(patched), len(self.archive))
        self.assertEqual(u8.read_file(patched, "kartParam.bin"), b"Z" * 40)
        self.assertEqual(u8.read_file(patched, "other.txt"), b"hello")

    def test_replace_rejects_size_change_and_missing_file(self):
        with self.assertRaises(ValueError):
            u8.replace_file(self.archive, "kartParam.bin", b"short")
        with self.assertRaises(KeyError):
            u8.replace_file(self.archive, "nope.bin", b"")


if __name__ == "__main__":
    unittest.main()
