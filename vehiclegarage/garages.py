"""Independent garages and portable, stats-only garage files."""

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import uuid
from dataclasses import replace
from pathlib import Path

from vehiclegarage import bmg
from vehiclegarage.creations import Creation, Library
from vehiclegarage.kartparam import FIELD_INDEX, _INT_FIELDS
from vehiclegarage.settings import library_dir
from vehiclegarage.stats import BARS
from vehiclegarage.textures import MAX_DOWNLOAD, TexturePack

FORMAT = "CustomVehicleGarage"
MAX_TRANSFER_SIZE = 8 * 1024 * 1024
MAX_VEHICLES = 10000
_ID = re.compile(r"[0-9a-f]{32}\Z")


def _write_json(path: Path, payload: dict) -> None:
    data = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as temp:
        temporary = Path(temp.name)
        try:
            temp.write(data)
        except BaseException:
            temp.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _name(name: str) -> str:
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > 80:
        raise ValueError("Garage names must contain 1 to 80 characters.")
    name = name.strip()
    if not bmg.valid_vehicle_name(name):
        raise ValueError("Garage names must contain printable characters.")
    return name


def _transfer_name(name: str, vehicle: bool) -> str:
    if not vehicle:
        return _name(name)
    if not isinstance(name, str) or name != name.strip() or not bmg.valid_vehicle_name(name):
        raise ValueError("Invalid vehicle name in the transfer file.")
    return name


def _validate_creation(data: object) -> Creation:
    if not isinstance(data, dict) or not {"name", "slot", "stats"} <= data.keys() or not data.keys() <= {
        "name", "slot", "stats", "number", "enabled", "texture",
    }:
        raise ValueError("Invalid vehicle entry in the imported file.")
    name, slot, stats = data["name"], data["slot"], data["stats"]
    number, enabled = data.get("number", 0), data.get("enabled", True)
    if not isinstance(name, str) or name != name.strip() or not bmg.valid_vehicle_name(name):
        raise ValueError("An imported vehicle has an invalid name.")
    if type(slot) is not int or not 0 <= slot < 36 or type(number) is not int or number < 0 or type(enabled) is not bool:
        raise ValueError(f"{name}: invalid slot, number, or inclusion setting.")
    if not isinstance(stats, dict) or not stats.keys() <= FIELD_INDEX.keys():
        raise ValueError(f"{name}: invalid stat fields.")
    for field, value in stats.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name}: {field} must be a number.")
        if FIELD_INDEX[field] in _INT_FIELDS:
            if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                raise ValueError(f"{name}: {field} must fit a 32-bit integer.")
        elif abs(value) > 3.402823466e38 or not math.isfinite(value):
            raise ValueError(f"{name}: {field} must fit a finite 32-bit float.")
        if field in ("tires", "weight_class"):
            maximum = {"tires": 3, "weight_class": 2}[field]
            if not 0 <= value <= maximum:
                raise ValueError(f"{name}: {field} must be between 0 and {maximum}.")
    for bar in BARS:
        if bar.field in stats:
            bar.to_display_rating(float(stats[bar.field]))
    try:
        texture = TexturePack.from_json(data["texture"]) if "texture" in data else None
    except (KeyError, TypeError) as err:
        raise ValueError(f"{name}: invalid texture description.") from err
    if texture is not None and type(texture.slot) is not int:
        raise ValueError(f"{name}: invalid texture slot.")
    return Creation(name=name, slot=slot, stats=stats, number=number, enabled=enabled, texture=texture)


def export_file(path: Path, name: str, items: list[Creation], *, vehicle: bool = False, fit_names: bool = False) -> None:
    if type(fit_names) is not bool:
        raise ValueError("The name-fitting setting must be on or off.")
    if len(items) > MAX_VEHICLES or (vehicle and len(items) != 1):
        raise ValueError("Invalid number of vehicles to export.")
    validated = [_validate_creation(item.to_json()) for item in items]
    payload = {
        "format": FORMAT, "version": 1, "kind": "vehicle" if vehicle else "garage",
        "name": _transfer_name(name, vehicle), "vehicles": [item.to_json() for item in validated], "fit_names": fit_names,
    }
    if len((json.dumps(payload, indent=2, ensure_ascii=False) + "\n").encode("utf-8")) > MAX_TRANSFER_SIZE:
        raise ValueError("The export file is too large.")
    _write_json(path, payload)


def import_file(path: Path) -> tuple[str, str, list[Creation], bool]:
    if path.stat().st_size > MAX_TRANSFER_SIZE:
        raise ValueError("The import file is too large.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Invalid garage file.")
    if data.keys() == {"version", "vehicles"}:
        from vehiclegarage import presets
        return "presets", "OnnY's Custom Vehicles", presets.read(path), True
    if (not {"format", "version", "kind", "name", "vehicles"} <= data.keys()
            or not data.keys() <= {"format", "version", "kind", "name", "vehicles", "fit_names"}
            or data["format"] != FORMAT or type(data["version"]) is not int or data["version"] != 1
            or data["kind"] not in ("garage", "vehicle") or type(data.get("fit_names", False)) is not bool):
        raise ValueError("Unsupported garage file format or version.")
    items = data["vehicles"]
    if not isinstance(items, list) or len(items) > MAX_VEHICLES or (data["kind"] == "vehicle" and len(items) != 1):
        raise ValueError("Invalid number of vehicles in the imported file.")
    return (data["kind"], _transfer_name(data["name"], data["kind"] == "vehicle"),
            [_validate_creation(item) for item in items], data.get("fit_names", False))


def missing_textures(items: list[Creation], storage: Path) -> list[str]:
    missing = []
    checked: dict[str, bool] = {}
    for item in items:
        if item.texture:
            for digest in item.texture.files.values():
                if digest not in checked:
                    path = storage / (digest + ".szs")
                    checked[digest] = (path.is_file() and path.stat().st_size <= MAX_DOWNLOAD
                                       and hashlib.sha256(path.read_bytes()).hexdigest() == digest)
                if not checked[digest]:
                    missing.append(item.name)
                    break
    return missing


class Garages:
    def __init__(self, root: Path):
        self.root = root
        self.index = root / "garages.json"
        self.folder = root / "garages"
        if not self.index.exists():
            self._initialise()
        self._data = self._read()

    def _initialise(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        legacy = library_dir(self.root)
        backup = self.root / "garage-migration-backup"
        if legacy.is_dir() and not backup.exists():
            with tempfile.TemporaryDirectory(prefix=".garage-backup-", dir=self.root) as tmp:
                target = Path(tmp) / "backup"
                target.mkdir()
                for path in legacy.glob("creation-*.json"):
                    shutil.copy2(path, target / path.name)
                os.replace(target, backup)
        _write_json(self.index, {"version": 1, "active": "default", "garages": [{"id": "default", "name": "My Garage", "fit_names": False}]})

    def _read(self) -> dict:
        data = json.loads(self.index.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.keys() != {"version", "active", "garages"}
                or type(data["version"]) is not int or data["version"] != 1 or not isinstance(data["garages"], list)
                or not data["garages"]):
            raise ValueError("Invalid garage index.")
        ids, names = set(), set()
        for item in data["garages"]:
            if (not isinstance(item, dict) or not {"id", "name"} <= item.keys()
                    or not item.keys() <= {"id", "name", "fit_names"}
                    or type(item.get("fit_names", False)) is not bool or not isinstance(item["id"], str)
                    or (item["id"] != "default" and not _ID.fullmatch(item["id"]))):
                raise ValueError("Invalid garage in index.")
            name = _name(item["name"])
            if name != item["name"] or item["id"] in ids or name.casefold() in names:
                raise ValueError("Duplicate or invalid garage in index.")
            ids.add(item["id"])
            names.add(name.casefold())
        if not isinstance(data["active"], str) or data["active"] not in ids:
            raise ValueError("The active garage is missing from the index.")
        return data

    def _save(self, data: dict) -> None:
        _write_json(self.index, data)
        self._data = data

    @property
    def active_id(self) -> str:
        return self._data["active"]

    @property
    def active_name(self) -> str:
        return self.name(self.active_id)

    def entries(self) -> list[tuple[str, str]]:
        return [(item["id"], item["name"]) for item in self._data["garages"]]

    def name(self, garage_id: str) -> str:
        for item in self._data["garages"]:
            if item["id"] == garage_id:
                return item["name"]
        raise ValueError("The garage no longer exists.")

    def library(self, garage_id: str | None = None) -> Library:
        garage_id = garage_id or self.active_id
        self.name(garage_id)
        return Library(library_dir(self.root) if garage_id == "default" else self.folder / garage_id / "creations")

    def fit_names(self, garage_id: str | None = None) -> bool:
        garage_id = garage_id or self.active_id
        self.name(garage_id)
        return next(item.get("fit_names", False) for item in self._data["garages"] if item["id"] == garage_id)

    def set_fit_names(self, enabled: bool) -> None:
        if type(enabled) is not bool:
            raise ValueError("The name-fitting setting must be on or off.")
        entries = [{**item, "fit_names": enabled} if item["id"] == self.active_id else item
                   for item in self._data["garages"]]
        self._save({**self._data, "garages": entries})

    def _unique_name(self, name: str, except_id: str = "") -> str:
        name = _name(name)
        if any(other.casefold() == name.casefold() and garage_id != except_id for garage_id, other in self.entries()):
            raise ValueError("A garage already has that name.")
        return name

    def select(self, garage_id: str) -> None:
        self.name(garage_id)
        self._save({**self._data, "active": garage_id})

    def create(self, name: str, items: list[Creation] | None = None, *, fit_names: bool = False) -> str:
        name = self._unique_name(name)
        if type(fit_names) is not bool:
            raise ValueError("The name-fitting setting must be on or off.")
        items = items or []
        if len(items) > MAX_VEHICLES:
            raise ValueError("Too many vehicles in this garage.")
        validated = [_validate_creation(item.to_json()) for item in items]
        self.folder.mkdir(parents=True, exist_ok=True)
        garage_id = uuid.uuid4().hex
        destination = self.folder / garage_id
        with tempfile.TemporaryDirectory(prefix=".new-", dir=self.folder) as tmp:
            stage = Path(tmp) / "garage"
            library = Library(stage / "creations")
            stage.mkdir()
            for number, item in enumerate(validated, 1):
                library.save(replace(item, number=number))
            os.replace(stage, destination)
        try:
            self._save({**self._data, "garages": [*self._data["garages"], {"id": garage_id, "name": name, "fit_names": fit_names}]})
        except BaseException:
            shutil.rmtree(destination)
            raise
        return garage_id

    def rename(self, garage_id: str, name: str) -> None:
        self.name(garage_id)
        name = self._unique_name(name, garage_id)
        entries = [{**item, "name": name} if item["id"] == garage_id else item for item in self._data["garages"]]
        self._save({**self._data, "garages": entries})

    def delete(self, garage_id: str) -> None:
        self.name(garage_id)
        if len(self._data["garages"]) == 1:
            raise ValueError("Keep at least one garage.")
        path = library_dir(self.root) if garage_id == "default" else self.folder / garage_id
        entries = [item for item in self._data["garages"] if item["id"] != garage_id]
        active = entries[0]["id"] if garage_id == self.active_id else self.active_id
        if path.is_symlink():
            raise ValueError("A garage folder cannot be a symbolic link.")
        staged = path.with_name(".deleted-" + uuid.uuid4().hex)
        exists = path.exists()
        if exists:
            os.replace(path, staged)
        try:
            self._save({**self._data, "active": active, "garages": entries})
        except BaseException:
            if exists:
                os.replace(staged, path)
            raise
        if exists:
            shutil.rmtree(staged)

    def file_vehicle(self, item: Creation, destination_id: str, *, move: bool = False) -> tuple[Creation, bool]:
        if destination_id == self.active_id:
            raise ValueError("Choose a different garage.")
        target = self.library(destination_id)
        conflict = item.enabled and any(c.enabled and c.slot == item.slot for c in target.all())
        copied = target.save(replace(_validate_creation(item.to_json()), number=0, enabled=item.enabled and not conflict))
        if move:
            try:
                self.library().delete(item.number)
            except OSError:
                target.delete(copied.number)
                raise
        return copied, conflict

    def add_vehicle(self, item: Creation) -> tuple[Creation, bool]:
        target = self.library()
        conflict = item.enabled and any(c.enabled and c.slot == item.slot for c in target.all())
        return target.save(replace(_validate_creation(item.to_json()), number=0, enabled=item.enabled and not conflict)), conflict
