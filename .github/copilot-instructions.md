# CustomVehicleGarage: Copilot instructions

CustomVehicleGarage is a PC tool that lets a player design vehicles and export them as a Mario Kart Wii Riivolution mod. The game only reads the 36 stock vehicle slots, so the tool writes creations into those slots. Creations are stored on the PC, never in the game.

## Layout

- `vehiclegarage/kartparam.py`: reads and writes `kartParam.bin` (big-endian, 396-byte sections).
- `vehiclegarage/yaz0.py`, `vehiclegarage/u8.py`: pure-Python Yaz0 codec and U8 reader. `u8.replace_file` patches a same-size file in place, so no archive repack is needed.
- `vehiclegarage/disc.py`: `import_game` pulls `Race/Common.szs`, seven `Scene/UI` archives containing vehicle parameters, and localized UI archives used for vehicle-name messages from an ISO, RVZ, WBFS or similar image with `DolphinTool extract -p DATA -s <path>`. They are cached under `%APPDATA%\CustomVehicleGarage\game\<gameid>\`.
- `vehiclegarage/vehicles.py`, `vehiclegarage/stats.py`: the 36 stock slots and stat editors (sliders plus exact numeric values, including over-range values; display ratings use the game's 0-20 scale).
- `vehiclegarage/machinepara.py`: reads the 27×7 character and 36×7 vehicle visual ratings in `machine_para.bin`; the menu bars are independent of gameplay stats.
- `vehiclegarage/creations.py`: `Creation` (name, slot, stat overrides, number, enabled) and `Library`, which stores numbered JSON files in `%APPDATA%\CustomVehicleGarage\creations\`.
- `vehiclegarage/export.py`: `build_mod` patches gameplay stats in `kartParam.bin`, display ratings in UI `machine_para.bin` files, and vehicle labels in localized `message/Common.bmg` files, then writes `CustomVehicleGarage/<disc path>` plus `riivolution/CustomVehicleGarage.xml`.
- `vehiclegarage/app.py`: the Tkinter app (My Garage, Create / Edit, Install Mod, Setup). `vehiclegarage/cli.py` opens it by default; `build --out <dir>` builds without a window.
- `garage.py` and `build_exe.ps1`: build `dist/CustomVehicleGarage.exe` with PyInstaller.
- `tests/`: `unittest` tests. Run with `python -m unittest discover -s tests -t . -v` from the project root.
- `ExampleMods/`: the Funny Vehicles reference mod (Riivolution XML, extracted SZS files, loader code). Treat it as read-only reference.

## Rules

- Use the `szs-archives`, `kartparam-slots`, and `riivolution-patch` skills in `.github/skills/` for file-format details.
- Game data is big-endian. Never read or write it with native-endian helpers.
- Never modify files under `ExampleMods/`. Write generated output to a separate output folder.
- Never commit or bundle game data. The app reads it from the user's own disc image at runtime.
- Keep edits surgical. Preserve unknown `kartParam.bin` bytes (the `Vehicle` class keeps raw bytes for this) and all unchanged character/vehicle ratings in `machine_para.bin`.
- The app must stay self-contained: standard library only, with Dolphin's `DolphinTool.exe` as the sole external program (it reads disc images).
- Add a test for each new format-handling behavior, and run the test suite before reporting work as done.
- Only comment code that needs clarification.
