"""Find the folders Dolphin already uses, so the mod lands where Dolphin looks without changing any root."""

import configparser
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from vehiclegarage.export import MOD_FOLDER


@dataclass(frozen=True)
class DolphinFolders:
    user_dir: Path
    riivolution: Path  # Load/Riivolution: the SD root Dolphin uses in "Start with Riivolution Patches"
    sd_sync: Path  # the folder Dolphin syncs with its emulated SD card


def user_dir(dolphin_exe: Path | None = None) -> Path:
    """Dolphin's user folder, using the same order Dolphin does on Windows."""
    if dolphin_exe and (dolphin_exe.parent / "portable.txt").exists():
        return dolphin_exe.parent / "User"
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Dolphin Emulator") as key:
            value, _ = winreg.QueryValueEx(key, "UserConfigPath")
            if value:
                return Path(value)
    except (ImportError, OSError):
        pass
    documents = Path.home() / "Documents" / "Dolphin Emulator"
    if documents.is_dir():
        return documents
    return Path(os.environ.get("APPDATA", str(Path.home()))) / "Dolphin Emulator"


def _setting(ini: Path, *names: str) -> str:
    parser = configparser.ConfigParser(strict=False, interpolation=None)
    parser.optionxform = str
    try:
        parser.read(ini, encoding="utf-8")
    except (OSError, configparser.Error):
        return ""
    for section in parser.sections():
        for name in names:
            value = parser.get(section, name, fallback="").strip()
            if value:
                return value
    return ""


def find_folders(dolphin_exe: Path | None = None) -> DolphinFolders:
    user = user_dir(dolphin_exe)
    load = user / "Load"
    configured = _setting(user / "Config" / "Dolphin.ini", "WiiSDCardSyncFolder", "WiiSDCardSyncFolderPath")
    return DolphinFolders(
        user_dir=user,
        riivolution=load / "Riivolution",
        sd_sync=Path(configured) if configured else load / "WiiSDSync",
    )


def launch_mod(exe: Path, image: Path, game_id: str, root: Path, preset: Path) -> None:
    """Launch the installed mod using Dolphin's game-mod preset format."""
    if not exe.is_file():
        raise ValueError("Dolphin.exe was not found beside the configured DolphinTool.exe.")
    if not image.is_file():
        raise ValueError("The configured game image was not found. Choose it on the Setup page.")
    xml = root / "riivolution" / f"{MOD_FOLDER}.xml"
    if not xml.is_file() or not (root / MOD_FOLDER).is_dir():
        raise ValueError("The Dolphin Riivolution installation is missing. Build the mod first.")
    try:
        patch = ElementTree.parse(xml).getroot()
    except ElementTree.ParseError as err:
        raise ValueError(f"The installed Riivolution XML is invalid: {err}") from err
    game = patch.find("id")
    choice = patch.find("./options/section[@name='Custom Vehicle Garage']/option[@name='Custom Vehicle Garage']/choice[@name='Enabled']/patch")
    patch_definition = patch.find("./patch[@id='customvehiclegarage']")
    if (game is None or game.get("game") != game_id[:4] or choice is None
            or choice.get("id") != "customvehiclegarage" or patch_definition is None):
        raise ValueError("The installed Riivolution patch does not match the selected game.")
    entries = patch_definition.findall("file")
    for entry in entries:
        external = entry.get("external", "")
        parts = external.split("/")
        if (len(parts) < 3 or parts[:2] != ["", MOD_FOLDER]
                or any(part in ("", ".", "..") or "\\" in part or ":" in part for part in parts[2:])
                or not root.joinpath(*parts[1:]).is_file()):
            raise ValueError(f"The installed Riivolution patch file is missing or invalid: {external}")
    preset_data = {
        "type": "dolphin-game-mod-descriptor",
        "version": 1,
        "base-file": str(image.resolve()),
        "display-name": "Custom Vehicle Garage",
        "riivolution": {
            "patches": [{
                "xml": str(xml.resolve()),
                "root": str(root.resolve()),
                "options": [{
                    "section-name": "Custom Vehicle Garage",
                    "option-name": "Custom Vehicle Garage",
                    "choice": 1,
                }],
            }],
        },
    }
    preset.parent.mkdir(parents=True, exist_ok=True)
    preset.write_text(json.dumps(preset_data, indent=2), encoding="utf-8")
    subprocess.Popen([str(exe), "--exec", str(preset.resolve())], cwd=str(exe.parent))
