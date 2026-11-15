"""Write creations into the game's vehicle slots and produce the Riivolution mod folder."""

import hashlib
import json
import os
import shutil
import tempfile
import threading
from contextlib import ExitStack
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import quoteattr

from vehiclegarage import bmg, textures, u8, yaz0
from vehiclegarage.creations import SLOT_COUNT, Creation, slot_conflicts
from vehiclegarage.disc import KARTPARAM_ARCHIVES, MACHINE_PARA_PATH, kartparam_archives, localized_message_archives
from vehiclegarage.kartparam import KartParam
from vehiclegarage.machinepara import MachinePara
from vehiclegarage.stats import BARS
from vehiclegarage.vehicles import VEHICLES

MOD_FOLDER = "CustomVehicleGarage"
VEHICLE_NAME_BMG_PATH = "message/Common.bmg"

Progress = Callable[[str, float], None]


class BuildCancelled(Exception):
    """The build was cancelled before installation began."""


class BuildCancellation:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cancelled = False
        self._committing = False

    def cancel(self) -> bool:
        with self._lock:
            if self._committing:
                return False
            self._cancelled = True
            return True

    def check(self) -> None:
        with self._lock:
            if self._cancelled:
                raise BuildCancelled()

    def begin_commit(self) -> None:
        with self._lock:
            if self._cancelled:
                raise BuildCancelled()
            self._committing = True


def build_kartparam(base: bytes, creations: list[Creation]) -> bytes:
    """Return a kartParam.bin where each creation's stats are written into its slot."""
    kart = KartParam.from_bytes(base)
    if len(kart.vehicles) != SLOT_COUNT:
        raise ValueError(f"expected {SLOT_COUNT} vehicle slots, got {len(kart.vehicles)}")
    for creation in creations:
        for name, value in creation.stats.items():
            kart.vehicles[creation.slot].set(name, value)
    return kart.to_bytes()


def build_machinepara(base: bytes, creations: list[Creation]) -> bytes:
    """Update visual stat bars for slider-backed stats without changing character or other slots."""
    machine = MachinePara(base)
    bars_by_field = {bar.field: bar for bar in BARS}
    for creation in creations:
        for field, bar in bars_by_field.items():
            if field in creation.stats:
                rating = bar.to_display_rating(float(creation.stats[field]))
                machine.set_vehicle_stat(creation.slot, bar.display_index, rating)
    return machine.raw


def build_vehicle_name_bmg(base: bytes, creations: list[Creation]) -> bytes:
    replacements = {}
    for creation in creations:
        if creation.name == VEHICLES[creation.slot].name:
            continue
        message_ids = bmg.vehicle_name_message_ids(creation.slot)
        current_names = {bmg.read_message(base, message_id) for message_id in message_ids}
        if len(current_names) != 1 or not next(iter(current_names)):
            raise ValueError(f"vehicle-name messages do not agree for slot {creation.slot}")
        replacements.update({message_id: creation.name for message_id in message_ids})
    return bmg.replace_messages(base, replacements) if replacements else base


def read_stock_kartparam(cache_game: Path) -> KartParam:
    """The unmodified vehicle table from the imported game's Common.szs."""
    data = yaz0.decompress((cache_game / "Race/Common.szs").read_bytes())
    return KartParam.from_bytes(u8.read_file(data, KARTPARAM_ARCHIVES["Race/Common.szs"]))


def patch_archive(szs: bytes, inner_path: str, creations: list[Creation], progress=None) -> bytes:
    """Patch vehicle stats and menu display bars in an archive, preserving all other files."""
    data = yaz0.decompress(szs)
    original = data
    patched = build_kartparam(u8.read_file(data, inner_path), creations)
    data = u8.replace_file(data, inner_path, patched)
    if MACHINE_PARA_PATH in u8.find_files(data):
        machine = build_machinepara(u8.read_file(data, MACHINE_PARA_PATH), creations)
        data = u8.replace_file(data, MACHINE_PARA_PATH, machine)
    return szs if data == original else yaz0.compress(data, progress)


def patch_vehicle_names_archive(szs: bytes, creations: list[Creation], progress=None) -> bytes:
    """Patch vehicle labels in a language-specific menu archive."""
    data = yaz0.decompress(szs)
    if VEHICLE_NAME_BMG_PATH not in u8.find_files(data):
        raise ValueError(f"archive is missing {VEHICLE_NAME_BMG_PATH}")
    base = u8.read_file(data, VEHICLE_NAME_BMG_PATH)
    patched = build_vehicle_name_bmg(base, creations)
    data = u8.replace_file(data, VEHICLE_NAME_BMG_PATH, patched)
    return szs if patched == base else yaz0.compress(data, progress)


def riivolution_xml(game_id: str, archives: list[str], title: str = "Custom Vehicle Garage") -> str:
    files = "".join(
        f'\t\t<file disc="/{a}" external="/{MOD_FOLDER}/{a}" resize="true" create="true"/>\n' for a in archives
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<wiidisc version="1">\n'
        f'\t<id game="{game_id[:4]}"/>\n'
        f"\t<options>\n\t\t<section name={quoteattr(title)}>\n"
        f"\t\t\t<option name={quoteattr(title)}>\n"
        '\t\t\t\t<choice name="Enabled">\n'
        '\t\t\t\t\t<patch id="customvehiclegarage"/>\n'
        "\t\t\t\t</choice>\n"
        "\t\t\t</option>\n\t\t</section>\n\t</options>\n"
        '\t<patch id="customvehiclegarage">\n'
        f"{files}"
        "\t</patch>\n"
        "</wiidisc>\n"
    )


def _build_staged(cache_game: Path, game_id: str, creations: list[Creation], out_root: Path,
                  progress: Progress | None, texture_dir: Path | None, cancel: BuildCancellation) -> None:
    active = [c for c in creations if c.enabled]
    conflicts = slot_conflicts(active)
    if conflicts:
        slot, items = next(iter(conflicts.items()))
        raise ValueError(f"slot {slot} is used by more than one creation: {', '.join(c.name for c in items)}")

    param_archives = kartparam_archives(game_id)
    available = [a for a in param_archives if (cache_game / a).is_file()]
    if active and any(c.stats for c in active):
        missing_params = [a for a in param_archives if a not in available]
        if missing_params:
            raise ValueError(
                "Re-import the game disc to load the vehicle parameter archives: "
                + ", ".join(missing_params)
            )
    renamed = [c for c in active if c.name != VEHICLES[c.slot].name]
    name_archives = localized_message_archives(game_id) if renamed else []
    if renamed and not name_archives:
        raise ValueError(f"vehicle name replacement is not supported for game ID {game_id}")
    missing = [archive for archive in name_archives if not (cache_game / archive).is_file()]
    if missing:
        raise ValueError(
            "Re-import the game disc to load the localized vehicle-name archives: "
            + ", ".join(missing)
        )

    cancel.check()
    texture_files = []
    for creation in active:
        cancel.check()
        if creation.texture:
            if texture_dir is None:
                raise ValueError("Texture storage was not provided for this build")
            texture_files.extend(textures.texture_outputs(creation.texture, creation.slot, texture_dir))
    texture_paths = [path for path, _ in texture_files]
    if len(set(texture_paths)) != len(texture_paths):
        raise ValueError("Multiple creations replace the same texture file")

    archives = [*(available if any(c.stats for c in active) else []), *name_archives]
    outputs = []
    for i, archive in enumerate(archives):
        def report(fraction: float, i=i, archive=archive):
            cancel.check()
            if progress:
                progress(f"Packing {archive}", (i + fraction) / len(archives))

        cancel.check()
        source = (cache_game / archive).read_bytes()
        is_param = archive in param_archives
        relevant = (
            [(c.slot, c.stats) for c in active if c.stats]
            if is_param else [(c.slot, c.name) for c in renamed]
        )
        key_data = json.dumps([1, archive, relevant], sort_keys=True, separators=(",", ":")).encode()
        key = hashlib.sha256(key_data + source).digest()
        cache_path = cache_game.parent / "build-cache" / game_id / (hashlib.sha256(archive.encode()).hexdigest() + ".bin")
        cached = cache_path.read_bytes() if cache_path.is_file() else b""
        if len(cached) >= 64 and cached[:32] == key and hashlib.sha256(cached[64:]).digest() == cached[32:64]:
            patched = cached[64:]
            report(1.0)
            outputs.append((archive, patched))
            continue
        if cached and cached[:32] == key and progress:
            progress(f"Rebuilding invalid cache for {archive}", i / len(archives))
        if archive in param_archives:
            patched = patch_archive(source, param_archives[archive], active, report)
        else:
            patched = patch_vehicle_names_archive(source, renamed, report)
        cancel.check()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=cache_path.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            try:
                temp.write(key + hashlib.sha256(patched).digest() + patched)
            except BaseException:
                temp.close()
                temp_path.unlink(missing_ok=True)
                raise
        try:
            os.replace(temp_path, cache_path)
        finally:
            temp_path.unlink(missing_ok=True)
        outputs.append((archive, patched))
    outputs.extend(texture_files)

    mod_dir = out_root / MOD_FOLDER
    for archive, patched in outputs:
        cancel.check()
        target = mod_dir / archive
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(patched)

    mod_dir.mkdir(parents=True, exist_ok=True)
    xml_dir = out_root / "riivolution"
    xml_dir.mkdir(parents=True, exist_ok=True)
    (xml_dir / f"{MOD_FOLDER}.xml").write_text(riivolution_xml(game_id, archives + texture_paths), encoding="utf-8")


def build_mod(cache_game: Path, game_id: str, creations: list[Creation], out_root: Path,
              progress: Progress | None = None, texture_dir: Path | None = None,
              cancel: BuildCancellation | None = None) -> Path:
    """Build and safely install into one output root."""
    install_mod(cache_game, game_id, creations, [out_root], progress, texture_dir, cancel)
    return out_root


def install_mod(cache_game: Path, game_id: str, creations: list[Creation], targets: list[Path],
                progress: Progress | None = None, texture_dir: Path | None = None,
                cancel: BuildCancellation | None = None) -> list[Path]:
    """Prepare every target before replacing any existing installation."""
    cancel = cancel or BuildCancellation()
    if not targets:
        raise ValueError("Choose at least one installation folder")
    resolved = [p.resolve() for p in targets]
    if len(set(resolved)) != len(resolved) or any(
        a in b.parents or b in a.parents for i, a in enumerate(resolved) for b in resolved[i + 1:]
    ):
        raise ValueError("Installation folders must be distinct and not nested")

    def copy_file(source, destination):
        with open(source, "rb") as src, open(destination, "wb") as dst:
            while True:
                cancel.check()
                chunk = src.read(1024 * 1024)
                if not chunk:
                    break
                dst.write(chunk)
        return destination

    with ExitStack() as stack:
        stages = []
        for target in targets:
            cancel.check()
            target.mkdir(parents=True, exist_ok=True)
            stages.append(Path(stack.enter_context(tempfile.TemporaryDirectory(prefix=".cvg-", dir=target))))
        _build_staged(cache_game, game_id, creations, stages[0], progress, texture_dir, cancel)
        for stage in stages[1:]:
            cancel.check()
            if progress:
                progress("Preparing installation folders", 1.0)
            shutil.copytree(stages[0] / MOD_FOLDER, stage / MOD_FOLDER, copy_function=copy_file)
            (stage / "riivolution").mkdir()
            copy_file(stages[0] / "riivolution" / f"{MOD_FOLDER}.xml", stage / "riivolution" / f"{MOD_FOLDER}.xml")
        cancel.begin_commit()
        if progress:
            progress("Finishing installation (cancellation unavailable)", 1.0)
        moved = []
        try:
            for target, stage in zip(targets, stages):
                (target / "riivolution").mkdir(exist_ok=True)
                for relative in (Path(MOD_FOLDER), Path("riivolution") / f"{MOD_FOLDER}.xml"):
                    destination = target / relative
                    backup = stage / ("backup-mod" if relative == Path(MOD_FOLDER) else "backup.xml")
                    had_old = destination.exists()
                    if had_old:
                        destination.rename(backup)
                    moved.append((destination, backup, had_old))
                    (stage / relative).rename(destination)
        except Exception as error:
            rollback_errors = []
            for destination, backup, had_old in reversed(moved):
                try:
                    if destination.is_dir():
                        shutil.rmtree(destination)
                    elif destination.exists():
                        destination.unlink()
                    if had_old:
                        backup.rename(destination)
                except OSError as rollback_error:
                    rollback_errors.append(str(rollback_error))
            if rollback_errors:
                recovery = []
                for stage in stages:
                    if (stage / "backup-mod").exists() or (stage / "backup.xml").exists():
                        recovery_path = stage.with_name(stage.name + "-recovery")
                        stage.rename(recovery_path)
                        recovery.append(str(recovery_path))
                raise RuntimeError(
                    f"Installation failed: {error}. Rollback failed: {'; '.join(rollback_errors)}. "
                    f"Backups retained at: {', '.join(recovery)}"
                ) from error
            raise
    return targets
