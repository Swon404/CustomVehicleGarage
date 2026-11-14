"""Stat bars shown in the garage, mapped onto real kartParam.bin fields.

Each bar is a 0-100 slider over a range of actual game values, so the slider is only
a view of the real number that gets written to the game.
"""

import math
from dataclasses import dataclass

from vehiclegarage.kartparam import FIELD_INDEX, _INT_FIELDS

DISPLAY_RATING_MAX = 20


@dataclass(frozen=True)
class StatBar:
    key: str
    label: str
    field: str
    low: float
    high: float
    hint: str
    display_index: int

    @property
    def is_int(self) -> bool:
        return FIELD_INDEX[self.field] in _INT_FIELDS

    def to_percent(self, value: float) -> float:
        pct = (value - self.low) / (self.high - self.low) * 100
        return max(0.0, min(100.0, pct))

    def from_percent(self, percent: float):
        value = self.low + (self.high - self.low) * percent / 100
        return round(value) if self.is_int else value

    def to_display_rating(self, value: float) -> int:
        """Map values to the game's menu scale, extending beyond the slider range."""
        rating = round((value - self.low) / (self.high - self.low) * DISPLAY_RATING_MAX)
        if not -32768 <= rating <= 32767:
            raise ValueError(f"{self.label} produces a menu rating outside the signed 16-bit range")
        return rating

    def parse_value(self, text: str) -> float | int:
        """Parse a numeric editor value, allowing values outside the slider range."""
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"{self.label} must be a number, got {text!r}") from None
        if not math.isfinite(value):
            raise ValueError(f"{self.label} must be a finite number")
        if self.is_int:
            if not value.is_integer():
                raise ValueError(f"{self.label} must be a whole number")
            integer = int(value)
            if not -(1 << 31) <= integer < (1 << 31):
                raise ValueError(f"{self.label} must fit a 32-bit integer")
            return integer
        if abs(value) > 3.402823466e38:
            raise ValueError(f"{self.label} must fit a 32-bit float")
        return value


BARS: tuple[StatBar, ...] = (
    StatBar("speed", "Speed", "speed", 65.0, 100.0, "Top speed on a straight", 0),
    StatBar("weight", "Weight", "weight", 1.5, 7.5, "Heavier karts push others around", 1),
    StatBar("accel", "Acceleration", "accel_a0", 0.10, 1.00, "How fast you pick up speed", 2),
    StatBar("handling", "Handling", "manual_handling", 0.01, 0.06, "Turning without drifting", 3),
    StatBar("drift", "Drift", "manual_drift", 0.005, 0.04, "Turning while drifting", 4),
    StatBar("offroad", "Off-Road", "speed_multiplier_3", 0.0, 1.0, "Speed retained on standard off-road", 5),
    StatBar("turbo", "Mini-Turbo", "mini_turbo_duration", 10, 60, "Mini-boost duration", 6),
)

# Extra single-value fields offered in the advanced editor.
ADVANCED_FIELDS: tuple[tuple[str, str, str], ...] = (
    ("bump_deviation", "Bumpiness", "How much the vehicle is thrown around by bumps"),
    ("speed_in_turn", "Speed in turns", "Speed while turning"),
    ("tilt", "Lean", "How far the vehicle leans in turns"),
    ("accel_a1", "Acceleration phase 2", "Second acceleration stage"),
    ("accel_a2", "Acceleration phase 3", "Third acceleration stage"),
    ("accel_a3", "Acceleration phase 4", "Fourth acceleration stage"),
    ("auto_handling", "Handling (auto)", "Turning with automatic steering"),
    ("handling_reactivity", "Handling reactivity", "How quickly steering responds"),
    ("auto_drift", "Drift (auto)", "Drifting with automatic steering"),
    ("drift_reactivity", "Drift reactivity", "How quickly drift steering responds"),
    ("drift_target_angle", "Drift angle", "Target angle while drifting"),
    ("max_normal_acceleration", "Max normal acceleration", "Cap on acceleration"),
    ("mega_mushroom_scale", "Mega size", "Size when mega"),
    ("shock_scale", "Shock size", "Size when shocked"),
)
