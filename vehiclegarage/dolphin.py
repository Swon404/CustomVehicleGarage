"""Find the folders Dolphin already uses, so the mod lands where Dolphin looks without changing any root."""

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


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
