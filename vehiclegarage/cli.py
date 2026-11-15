"""Entry point: `python -m vehiclegarage` opens the app; `build` makes the mod without a window."""

import argparse
import sys
from pathlib import Path

from vehiclegarage import disc, export
from vehiclegarage.creations import Library
from vehiclegarage.settings import Settings, cache_dir, data_dir, library_dir, texture_dir


def build(args: argparse.Namespace) -> int:
    root = Path(args.data) if args.data else data_dir()
    settings = Settings.load(root)
    if args.disc:
        tool = Path(args.dolphintool or settings.dolphintool or disc.find_dolphintool() or "")
        settings.game_id = disc.import_game(tool, Path(args.disc), cache_dir(root))
        settings.save(root)
    if not settings.game_id:
        print("error: import a game first with --disc", file=sys.stderr)
        return 1
    creations = Library(library_dir(root)).all()
    out = export.build_mod(cache_dir(root) / settings.game_id, settings.game_id, creations, Path(args.out), texture_dir=texture_dir(root))
    print(f"wrote mod to {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vehiclegarage")
    parser.add_argument("--data", help="data folder (default: %%APPDATA%%\\CustomVehicleGarage)")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="open the garage app (default)")
    b = sub.add_parser("build", help="build the mod from saved creations without opening the app")
    b.add_argument("--out", required=True, help="SD card root or Dolphin Load/Riivolution folder")
    b.add_argument("--disc", help="import this game image first")
    b.add_argument("--dolphintool", help="path to DolphinTool.exe")
    b.set_defaults(func=build)

    args = parser.parse_args(argv)
    if args.command == "build":
        try:
            return args.func(args)
        except (ValueError, RuntimeError, OSError) as err:
            print(f"error: {err}", file=sys.stderr)
            return 1
    from vehiclegarage import app

    app.main(Path(args.data) if args.data else None)
    return 0
