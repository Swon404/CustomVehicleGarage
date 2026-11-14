"""Read the game's files straight from a disc image using Dolphin's DolphinTool.

DolphinTool opens ISO, WBFS, RVZ, WIA, GCZ and CISO images, so no conversion or
extra extraction tools are needed. Only the few archives the mod edits are pulled out.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

# Disc path of each archive -> path of its kartParam.bin inside the archive.
KARTPARAM_ARCHIVES = {
    "Race/Common.szs": "kartParam.bin",
    "Scene/UI/MenuSingle.szs": "parameter/kartParam.bin",
    "Scene/UI/MenuMulti.szs": "parameter/kartParam.bin",
    "Scene/UI/Globe.szs": "parameter/kartParam.bin",
    "Scene/UI/Award.szs": "parameter/kartParam.bin",
    "Scene/UI/Event.szs": "parameter/kartParam.bin",
    "Scene/UI/MenuOther.szs": "parameter/kartParam.bin",
    "Scene/UI/Present.szs": "parameter/kartParam.bin",
}
MACHINE_PARA_ARCHIVES = tuple(path for path in KARTPARAM_ARCHIVES if path.startswith("Scene/UI/"))
MACHINE_PARA_PATH = "parameter/machine_para.bin"
REQUIRED_ARCHIVE = "Race/Common.szs"
MESSAGE_ARCHIVE_STEMS = (
    "Award",
    "Channel",
    "Event",
    "Globe",
    "MenuMulti",
    "MenuOther",
    "MenuSingle",
    "Present",
    "Race",
    "Title",
)
LANGUAGE_SUFFIXES_BY_REGION = {
    "E": ("M", "Q", "U"),
    "P": ("E", "F", "G", "I", "S"),
    "J": ("J",),
    "K": ("K", "R"),
}

_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class DiscError(RuntimeError):
    pass


def localized_message_archives(game_id: str) -> list[str]:
    suffixes = LANGUAGE_SUFFIXES_BY_REGION.get(game_id[3:4], ())
    return [
        f"Scene/UI/{stem}_{suffix}.szs"
        for suffix in suffixes
        for stem in MESSAGE_ARCHIVE_STEMS
    ]


def find_dolphintool(extra_dirs: list[Path] | None = None) -> Path | None:
    """Look for DolphinTool.exe in the given folders (and their parents' siblings), common installs, and PATH."""
    candidates: list[Path] = []
    for d in extra_dirs or []:
        d = Path(d)
        candidates.append(d / "DolphinTool.exe")
        for neighbour in (d, d.parent):
            try:
                candidates += [c / "DolphinTool.exe" for c in neighbour.iterdir() if c.is_dir()]
            except OSError:
                pass
    for env, rel in (
        ("LOCALAPPDATA", "Programs/Dolphin"),
        ("ProgramFiles", "Dolphin"),
        ("ProgramFiles(x86)", "Dolphin"),
    ):
        if os.environ.get(env):
            candidates.append(Path(os.environ[env]) / rel / "DolphinTool.exe")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    found = shutil.which("DolphinTool") or shutil.which("dolphin-tool")
    return Path(found) if found else None


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, creationflags=_NO_WINDOW)


def read_game_id(dolphintool: Path, disc: Path) -> str:
    result = _run([str(dolphintool), "header", "-i", str(disc), "-j"])
    if result.returncode != 0:
        raise DiscError(f"DolphinTool could not read {disc.name}: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)["game_id"]


def import_game(dolphintool: Path, disc: Path, cache: Path) -> str:
    """Copy the archives the mod needs from the disc into `cache`; return the game ID."""
    game_id = read_game_id(dolphintool, disc)
    if not game_id.startswith("RMC"):
        raise DiscError(f"{disc.name} is {game_id}, not Mario Kart Wii (RMC...)")
    target = cache / game_id
    if target.exists():
        shutil.rmtree(target)
    staging = cache / "_staging"
    localized_archives = localized_message_archives(game_id)
    required_localized = set(localized_archives)
    for archive in [*KARTPARAM_ARCHIVES, *localized_archives]:
        if staging.exists():
            shutil.rmtree(staging)
        result = _run([str(dolphintool), "extract", "-i", str(disc), "-o", str(staging), "-p", "DATA", "-s", archive])
        extracted = staging / "DATA" / "files" / Path(archive)
        if not extracted.is_file():
            if archive == REQUIRED_ARCHIVE or archive in required_localized:
                raise DiscError(f"{archive} was not found on the disc: {result.stderr.strip() or result.stdout.strip()}")
            continue
        destination = target / archive
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(extracted), str(destination))
    shutil.rmtree(staging, ignore_errors=True)
    (target / "source.json").write_text(json.dumps({"disc": disc.name}), encoding="utf-8")
    return game_id


def cached_games(cache: Path) -> list[str]:
    if not cache.is_dir():
        return []
    return sorted(p.name for p in cache.iterdir() if (p / REQUIRED_ARCHIVE).is_file())
