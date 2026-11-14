"""Read and update the stat ratings shown by Mario Kart Wii's menus."""

import struct
from dataclasses import dataclass

CHARACTER_COUNT = 27
VEHICLE_COUNT = 36
STAT_COUNT = 7
CHARACTER_SIZE = CHARACTER_COUNT * STAT_COUNT * 2
VEHICLE_SIZE = VEHICLE_COUNT * STAT_COUNT * 2
VEHICLE_OFFSET = CHARACTER_SIZE
FILE_SIZE = CHARACTER_SIZE + VEHICLE_SIZE


@dataclass
class MachinePara:
    """Character and vehicle display ratings stored as signed big-endian int16s."""

    raw: bytes

    def __post_init__(self):
        if len(self.raw) != FILE_SIZE:
            raise ValueError(f"machine_para.bin must be {FILE_SIZE} bytes, got {len(self.raw)}")

    def vehicle_stat(self, slot: int, stat: int) -> int:
        self._validate_index(slot, stat)
        offset = VEHICLE_OFFSET + (slot * STAT_COUNT + stat) * 2
        return struct.unpack_from(">h", self.raw, offset)[0]

    def set_vehicle_stat(self, slot: int, stat: int, value: int) -> None:
        self._validate_index(slot, stat)
        if not -32768 <= value <= 32767:
            raise ValueError(f"display rating must fit a signed 16-bit integer, got {value}")
        data = bytearray(self.raw)
        offset = VEHICLE_OFFSET + (slot * STAT_COUNT + stat) * 2
        struct.pack_into(">h", data, offset, value)
        self.raw = bytes(data)

    @staticmethod
    def _validate_index(slot: int, stat: int) -> None:
        if not 0 <= slot < VEHICLE_COUNT:
            raise ValueError(f"vehicle slot {slot} is outside 0..{VEHICLE_COUNT - 1}")
        if not 0 <= stat < STAT_COUNT:
            raise ValueError(f"display stat {stat} is outside 0..{STAT_COUNT - 1}")
