"""OnnY's separate collection of 36 example vehicle builds."""

import json
import math
import os
import tempfile
from dataclasses import replace
from pathlib import Path

from vehiclegarage import bmg, disc, u8, yaz0
from vehiclegarage.creations import Creation
from vehiclegarage.export import VEHICLE_NAME_BMG_PATH
from vehiclegarage.kartparam import FIELD_INDEX, _INT_FIELDS
from vehiclegarage.stats import ADVANCED_FIELDS, BARS
from vehiclegarage.vehicles import VEHICLES

DEFAULT_FILE = Path(__file__).resolve().parent / "assets" / "onny-presets.json"
DRAFT_FILE = "onny-presets-draft.json"
_BAR_FIELDS = {bar.field for bar in BARS}
_EDITABLE_FIELDS = _BAR_FIELDS | {field for field, _, _ in ADVANCED_FIELDS}


def _validate(items: list[Creation]) -> None:
    if len(items) != len(VEHICLES) or {item.slot for item in items} != set(range(len(VEHICLES))):
        raise ValueError("The preset collection must contain each of the 36 vehicle slots exactly once.")
    for item in items:
        if (type(item.slot) is not int or not isinstance(item.name, str)
                or not bmg.valid_vehicle_name(item.name) or item.name != item.name.strip()
                or item.texture is not None or not item.enabled or item.number != 0):
            raise ValueError("Invalid preset slot, name, or unsupported texture.")
        if not isinstance(item.stats, dict) or not _BAR_FIELDS <= item.stats.keys() or not item.stats.keys() <= _EDITABLE_FIELDS:
            raise ValueError(f"{item.name}: preset stats must include all seven performance values.")
        for field, value in item.stats.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{item.name}: {field} must be a number.")
            if FIELD_INDEX[field] in _INT_FIELDS:
                if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                    raise ValueError(f"{item.name}: {field} must fit a 32-bit integer.")
            elif abs(value) > 3.402823466e38 or not math.isfinite(value):
                raise ValueError(f"{item.name}: {field} must fit a finite 32-bit float.")
        for bar in BARS:
            bar.to_display_rating(float(item.stats[bar.field]))


def read(path: Path) -> list[Creation]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.keys() != {"version", "vehicles"}
            or type(data["version"]) is not int or data["version"] != 1):
        raise ValueError(f"Invalid preset collection: {path}")
    vehicles = data["vehicles"]
    if not isinstance(vehicles, list):
        raise ValueError(f"Invalid preset collection: {path}")
    items = []
    for entry in vehicles:
        if (not isinstance(entry, dict) or entry.keys() != {"slot", "name", "stats"}
                or type(entry["slot"]) is not int or not 0 <= entry["slot"] < len(VEHICLES)
                or not isinstance(entry["name"], str) or not isinstance(entry["stats"], dict)):
            raise ValueError(f"Invalid preset entry in {path}")
        items.append(Creation(name=entry["name"], slot=entry["slot"], stats=entry["stats"]))
    _validate(items)
    return sorted(items, key=lambda item: item.slot)


def creations(draft_root: Path | None = None) -> list[Creation]:
    draft = draft_root / DRAFT_FILE if draft_root is not None else None
    return read(draft if draft is not None and draft.is_file() else DEFAULT_FILE)


def write(path: Path, items: list[Creation]) -> None:
    _validate(items)
    payload = {
        "version": 1,
        "vehicles": [
            {"slot": item.slot, "name": item.name, "stats": item.stats}
            for item in sorted(items, key=lambda item: item.slot)
        ],
    }
    data = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temp_path = Path(temp.name)
        try:
            temp.write(data)
        except BaseException:
            temp.close()
            temp_path.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def save_draft(root: Path, item: Creation) -> None:
    items = creations(root)
    if type(item.slot) is not int or not 0 <= item.slot < len(items):
        raise ValueError("Invalid preset slot.")
    items[item.slot] = item
    root.mkdir(parents=True, exist_ok=True)
    write(root / DRAFT_FILE, items)


def fit_names(items: list[Creation], cache_game: Path, game_id: str, check) -> tuple[list[Creation], list[str]]:
    capacities: list[int | None] = [None] * len(VEHICLES)
    for archive in disc.localized_message_archives(game_id):
        check()
        path = cache_game / archive
        if not path.is_file():
            raise ValueError(f"Re-import the game disc to load the localized vehicle-name archive: {archive}")
        data = yaz0.decompress(path.read_bytes())
        limits = bmg.vehicle_name_capacities(u8.read_file(data, VEHICLE_NAME_BMG_PATH))
        for slot, limit in enumerate(limits):
            previous = capacities[slot]
            capacities[slot] = limit if previous is None else min(previous, limit)
    result = []
    shortened = []
    for item in items:
        limit = capacities[item.slot]
        if limit is None or limit < 1:
            raise ValueError(f"No name space is available for {VEHICLES[item.slot].name}.")
        units = 0
        end = 0
        for char in item.name:
            count = len(char.encode("utf-16-be")) // 2
            if units + count > limit:
                break
            units += count
            end += 1
        name = item.name[:end].rstrip()
        if not name:
            raise ValueError(f"The preset name for {VEHICLES[item.slot].name} does not fit its available space.")
        if name != item.name:
            shortened.append(f"{item.name} -> {name}")
        result.append(replace(item, name=name))
    return result, shortened
