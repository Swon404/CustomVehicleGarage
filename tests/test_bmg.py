import struct
import unittest

from vehiclegarage.bmg import (
    read_message,
    replace_messages,
    valid_vehicle_name,
    vehicle_name_message_ids,
)


def _section(kind: bytes, payload: bytes) -> bytes:
    padding = (-(8 + len(payload))) % 32
    size = 8 + len(payload) + padding
    return kind + struct.pack(">I", size) + payload + bytes(padding)


def build_bmg(messages: list[tuple[int, str]]) -> bytes:
    pool = bytearray()
    entries = bytearray()
    message_ids = bytearray()
    for message_id, text in messages:
        entries += struct.pack(">II", len(pool), 0x01000000)
        pool += text.encode("utf-16-be") + b"\0\0"
        message_ids += struct.pack(">I", message_id)

    inf = _section(
        b"INF1",
        struct.pack(">HHHBB", len(messages), 8, 0, 0, 0) + entries,
    )
    dat = _section(b"DAT1", bytes(pool))
    mid = _section(b"MID1", struct.pack(">HHI", len(messages), 0x1000, 0) + message_ids)
    data = bytearray(0x20)
    data[:8] = b"MESGbmg1"
    struct.pack_into(">II", data, 8, 0x20 + len(inf) + len(dat) + len(mid), 3)
    data[0x10] = 2
    return bytes(data) + inf + dat + mid


class BmgTests(unittest.TestCase):
    def test_name_accepts_longer_text_and_rejects_invalid_characters(self):
        self.assertTrue(valid_vehicle_name("Standard Kart S"))
        self.assertTrue(valid_vehicle_name("🚗" * 6))
        self.assertFalse(valid_vehicle_name("Bad\nName"))
        self.assertFalse(valid_vehicle_name("\ud800"))

    def test_replaces_vehicle_name_messages_without_resizing(self):
        source = build_bmg(
            [
                (9100, "Standard Kart S"),
                (9118, "Standard Kart S"),
                (9121, "Standard Kart S"),
                (9101, "Standard Kart M"),
            ]
        )
        replacements = {message_id: "Garage Kart" for message_id in vehicle_name_message_ids(0)}
        patched = replace_messages(source, replacements)
        self.assertEqual(len(patched), len(source))
        for message_id in replacements:
            self.assertEqual(read_message(patched, message_id), "Garage Kart")
        self.assertEqual(read_message(patched, 9101), "Standard Kart M")

    def test_long_name_is_allowed_when_existing_slot_has_space(self):
        source = build_bmg([(9100, "A long original name"), (9101, "Other")])
        patched = replace_messages(source, {9100: "Longer than ten"})
        self.assertEqual(read_message(patched, 9100), "Longer than ten")
        self.assertEqual(len(patched), len(source))

    def test_rejects_names_that_do_not_fit_and_unexpected_stock_text(self):
        source = build_bmg([(9100, "Standard Kart S"), (9101, "Standard Kart M")])
        with self.assertRaisesRegex(ValueError, "too long"):
            replace_messages(source, {9100: "X" * 40})

    def test_vehicle_name_ids_include_duplicate_stock_label_entries(self):
        self.assertEqual(vehicle_name_message_ids(0), (9100, 9118, 9121))
        self.assertEqual(vehicle_name_message_ids(18), (9150, 9168, 9171))
        self.assertEqual(vehicle_name_message_ids(35), (9167,))
        with self.assertRaises(ValueError):
            vehicle_name_message_ids(36)


if __name__ == "__main__":
    unittest.main()
