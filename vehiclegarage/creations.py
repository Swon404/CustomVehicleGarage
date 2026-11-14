"""Save and load custom vehicle creations as JSON on the PC."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from vehiclegarage.kartparam import FIELD_INDEX

SLOT_COUNT = 36


@dataclass
class Creation:
    name: str
    stats: dict[str, float | int] = field(default_factory=dict)
    slot: int = 0
    number: int = 0
    enabled: bool = True

    def __post_init__(self):
        unknown = set(self.stats) - set(FIELD_INDEX)
        if unknown:
            raise ValueError(f"unknown stat fields: {sorted(unknown)}")
        if not 0 <= self.slot < SLOT_COUNT:
            raise ValueError(f"slot {self.slot} is outside 0..{SLOT_COUNT - 1}")

    def to_json(self) -> dict:
        return {
            "number": self.number,
            "name": self.name,
            "slot": self.slot,
            "enabled": self.enabled,
            "stats": self.stats,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Creation":
        return cls(
            name=data["name"],
            stats=data.get("stats", {}),
            slot=data.get("slot", 0),
            number=data.get("number", 0),
            enabled=data.get("enabled", True),
        )


class Library:
    """A folder of creations, each numbered from the next free number."""

    def __init__(self, folder: Path):
        self.folder = folder

    def _path(self, number: int) -> Path:
        return self.folder / f"creation-{number:03d}.json"

    def all(self) -> list[Creation]:
        if not self.folder.is_dir():
            return []
        items = [Creation.from_json(json.loads(p.read_text(encoding="utf-8"))) for p in self.folder.glob("creation-*.json")]
        return sorted(items, key=lambda c: c.number)

    def next_number(self) -> int:
        return max((c.number for c in self.all()), default=0) + 1

    def save(self, creation: Creation) -> Creation:
        """Write a creation, giving it the next number if it has none."""
        if creation.number <= 0:
            creation.number = self.next_number()
        self.folder.mkdir(parents=True, exist_ok=True)
        self._path(creation.number).write_text(json.dumps(creation.to_json(), indent=2), encoding="utf-8")
        return creation

    def delete(self, number: int) -> None:
        self._path(number).unlink(missing_ok=True)


def slot_conflicts(creations: list[Creation]) -> dict[int, list[Creation]]:
    """Slots claimed by more than one enabled creation."""
    claims: dict[int, list[Creation]] = {}
    for c in creations:
        if c.enabled:
            claims.setdefault(c.slot, []).append(c)
    return {slot: items for slot, items in claims.items() if len(items) > 1}
