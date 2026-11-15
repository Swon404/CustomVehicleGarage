"""Where the app keeps its data and remembers the user's choices."""

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


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
