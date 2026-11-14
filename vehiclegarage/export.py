"""Write creations into the game's vehicle slots and produce the Riivolution mod folder."""

import shutil
from collections.abc import Callable
from pathlib import Path
from xml.sax.saxutils import quoteattr

from vehiclegarage import bmg, u8, yaz0
from vehiclegarage.creations import SLOT_COUNT, Creation, slot_conflicts
from vehiclegarage.disc import KARTPARAM_ARCHIVES, MACHINE_PARA_PATH, localized_message_archives
from vehiclegarage.kartparam import KartParam
from vehiclegarage.machinepara import MachinePara
from vehiclegarage.stats import BARS
from vehiclegarage.vehicles import VEHICLES

MOD_FOLDER = "CustomVehicleGarage"
VEHICLE_NAME_BMG_PATH = "message/Common.bmg"

Progress = Callable[[str, float], None]


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
    patched = build_kartparam(u8.read_file(data, inner_path), creations)
    data = u8.replace_file(data, inner_path, patched)
    if MACHINE_PARA_PATH in u8.find_files(data):
        machine = build_machinepara(u8.read_file(data, MACHINE_PARA_PATH), creations)
        data = u8.replace_file(data, MACHINE_PARA_PATH, machine)
    return yaz0.compress(data, progress)


def patch_vehicle_names_archive(szs: bytes, creations: list[Creation], progress=None) -> bytes:
    """Patch vehicle labels in a language-specific menu archive."""
    data = yaz0.decompress(szs)
    if VEHICLE_NAME_BMG_PATH not in u8.find_files(data):
        raise ValueError(f"archive is missing {VEHICLE_NAME_BMG_PATH}")
    base = u8.read_file(data, VEHICLE_NAME_BMG_PATH)
    patched = build_vehicle_name_bmg(base, creations)
    data = u8.replace_file(data, VEHICLE_NAME_BMG_PATH, patched)
    return yaz0.compress(data, progress)


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


def build_mod(cache_game: Path, game_id: str, creations: list[Creation], out_root: Path, progress: Progress | None = None) -> Path:
    """Write the mod into `out_root` (an SD card root or Dolphin's Riivolution folder)."""
    active = [c for c in creations if c.enabled]
    conflicts = slot_conflicts(active)
    if conflicts:
        slot, items = next(iter(conflicts.items()))
        raise ValueError(f"slot {slot} is used by more than one creation: {', '.join(c.name for c in items)}")

    available = [a for a in KARTPARAM_ARCHIVES if (cache_game / a).is_file()]
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

    archives = [*available, *name_archives]
    outputs = []
    for i, archive in enumerate(archives):
        def report(fraction: float, i=i, archive=archive):
            if progress:
                progress(f"Packing {archive}", (i + fraction) / len(archives))

        if archive in KARTPARAM_ARCHIVES:
            patched = patch_archive((cache_game / archive).read_bytes(), KARTPARAM_ARCHIVES[archive], active, report)
        else:
            patched = patch_vehicle_names_archive((cache_game / archive).read_bytes(), renamed, report)
        outputs.append((archive, patched))

    mod_dir = out_root / MOD_FOLDER
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
    for archive, patched in outputs:
        target = mod_dir / archive
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(patched)

    xml_dir = out_root / "riivolution"
    xml_dir.mkdir(parents=True, exist_ok=True)
    (xml_dir / f"{MOD_FOLDER}.xml").write_text(riivolution_xml(game_id, archives), encoding="utf-8")
    return out_root


def install_mod(cache_game: Path, game_id: str, creations: list[Creation], targets: list[Path], progress: Progress | None = None) -> list[Path]:
    """Build the mod once into the first target, then copy the result into the others."""
    first, *rest = targets
    build_mod(cache_game, game_id, creations, first, progress)
    for target in rest:
        if (target / MOD_FOLDER).exists():
            shutil.rmtree(target / MOD_FOLDER)
        shutil.copytree(first / MOD_FOLDER, target / MOD_FOLDER)
        (target / "riivolution").mkdir(parents=True, exist_ok=True)
        shutil.copy2(first / "riivolution" / f"{MOD_FOLDER}.xml", target / "riivolution" / f"{MOD_FOLDER}.xml")
    return targets
