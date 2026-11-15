"""Where the app keeps its data and remembers the user's choices."""

import json
import os
import ctypes
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path


def downloads_dir() -> Path:
    if os.name == "nt":
        folder_id = (ctypes.c_byte * 16).from_buffer_copy(
            uuid.UUID("374de290-123f-4565-9164-39c4925e467b").bytes_le
        )
        result = ctypes.c_void_p()
        shell = ctypes.windll.shell32
        shell.SHGetKnownFolderPath.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
        shell.SHGetKnownFolderPath.restype = ctypes.c_long
        status = shell.SHGetKnownFolderPath(ctypes.byref(folder_id), 0, None, ctypes.byref(result))
        if status != 0:
            raise OSError(f"Could not locate the Windows Downloads folder (error {status:#x}).")
        try:
            folder = Path(ctypes.wstring_at(result))
        finally:
            ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            ctypes.windll.ole32.CoTaskMemFree(result)
    else:
        folder = Path.home() / "Downloads"
    return folder if folder.is_dir() else Path.home()


def data_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return Path(base) / "CustomVehicleGarage"


@dataclass
class Settings:
    disc: str = ""
    dolphintool: str = ""
    output: str = ""
    install_riivolution: bool = True
    install_sd_sync: bool = True
    install_custom: bool = False
    game_id: str = ""
    recent_folders: dict[str, str] = field(default_factory=dict)
    build_collection: str = ""

    def picker_folder(self, key: str, existing: str = "", is_file: bool = False) -> Path:
        remembered = self.recent_folders.get(key)
        if remembered and Path(remembered).is_dir():
            return Path(remembered)
        if existing:
            candidate = Path(existing).parent if is_file else Path(existing)
            if candidate.is_dir():
                return candidate
        return downloads_dir()

    def remember_folder(self, key: str, chosen: str, is_file: bool, root: Path | None = None) -> None:
        if chosen:
            self.recent_folders[key] = str(Path(chosen).parent if is_file else Path(chosen))
            self.save(root)

    @classmethod
    def load(cls, root: Path | None = None) -> "Settings":
        path = (root or data_dir()) / "settings.json"
        if not path.is_file():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def save(self, root: Path | None = None) -> None:
        root = root or data_dir()
        root.mkdir(parents=True, exist_ok=True)
        (root / "settings.json").write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


def library_dir(root: Path | None = None) -> Path:
    return (root or data_dir()) / "creations"


def cache_dir(root: Path | None = None) -> Path:
    return (root or data_dir()) / "game"


def texture_dir(root: Path | None = None) -> Path:
    return (root or data_dir()) / "textures"
