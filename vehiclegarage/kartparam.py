"""Read and write Mario Kart Wii kartParam.bin vehicle stat tables."""

import struct
from dataclasses import dataclass, field

SECTION_WORDS = 99
SECTION_SIZE = SECTION_WORDS * 4

# Word index -> name for scalar fields (values are 32-bit words at index * 4).
_INT_FIELDS = {0: "tires", 1: "drift_type", 2: "weight_class", 27: "mini_turbo_duration"}
_FLOAT_FIELDS = {
    3: "unknown_always_50",
    4: "weight",
    5: "bump_deviation",
    6: "speed",
    7: "speed_in_turn",
    8: "tilt",
    9: "accel_a0",
    10: "accel_a1",
    11: "accel_a2",
    12: "accel_a3",
    13: "accel_t1",
    14: "accel_t2",
    15: "accel_t3",
    16: "drift_accel_a0",
    17: "drift_accel_a1",
    18: "drift_accel_t1",
    19: "manual_handling",
    20: "auto_handling",
    21: "handling_reactivity",
    22: "manual_drift",
    23: "auto_drift",
    24: "drift_reactivity",
    25: "drift_target_angle",
    26: "drift_decrement",
    92: "rotating_items_z_radius",
    93: "rotating_items_x_radius",
    94: "rotating_items_y_distance",
    95: "rotating_items_z_distance",
    96: "max_normal_acceleration",
    97: "mega_mushroom_scale",
    98: "shock_scale",
}
# 32 KCL-flag entries each: speed multipliers (words 28-59), rotation multipliers (60-91).
for _i in range(32):
    _FLOAT_FIELDS[28 + _i] = f"speed_multiplier_{_i}"
    _FLOAT_FIELDS[60 + _i] = f"rotation_multiplier_{_i}"

FIELD_INDEX = {**{v: k for k, v in _INT_FIELDS.items()}, **{v: k for k, v in _FLOAT_FIELDS.items()}}


@dataclass
class Vehicle:
    """One 396-byte vehicle section, kept as raw bytes so untouched fields survive a round trip."""

    raw: bytes = field(repr=False)

    def __post_init__(self):
        if len(self.raw) != SECTION_SIZE:
            raise ValueError(f"vehicle section must be {SECTION_SIZE} bytes, got {len(self.raw)}")

    def get(self, name: str):
        index = FIELD_INDEX[name]
        fmt = ">i" if index in _INT_FIELDS else ">f"
        return struct.unpack_from(fmt, self.raw, index * 4)[0]

    def set(self, name: str, value) -> None:
        index = FIELD_INDEX[name]
        fmt = ">i" if index in _INT_FIELDS else ">f"
        buf = bytearray(self.raw)
        struct.pack_into(fmt, buf, index * 4, value)
        self.raw = bytes(buf)


@dataclass
class KartParam:
    vehicles: list[Vehicle]

    @classmethod
    def from_bytes(cls, data: bytes) -> "KartParam":
        (count,) = struct.unpack_from(">I", data, 0)
        expected = 4 + count * SECTION_SIZE
        if len(data) != expected:
            raise ValueError(f"kartParam.bin with {count} vehicles must be {expected} bytes, got {len(data)}")
        vehicles = [
            Vehicle(data[4 + i * SECTION_SIZE : 4 + (i + 1) * SECTION_SIZE]) for i in range(count)
        ]
        return cls(vehicles)

    def to_bytes(self) -> bytes:
        return struct.pack(">I", len(self.vehicles)) + b"".join(v.raw for v in self.vehicles)
