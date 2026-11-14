# Custom Vehicle Garage

Design your own Mario Kart Wii vehicles on the PC and install them as a Riivolution mod. Creations replace the game's 36 stock vehicles, so you choose which stock vehicle each one takes over.

## Use it

1. Run `dist\CustomVehicleGarage.exe` (or `python -m vehiclegarage`).
2. **Setup** (first run): pick your own Mario Kart Wii image (ISO, RVZ, WBFS...) and `DolphinTool.exe` (it comes with Dolphin), then import. Nothing from the game ships with this app.
3. **My Garage**: create a vehicle, search saved creations by name or weight class, edit them, or include/exclude them from the mod.
4. **Choose Vehicle**: pick the stock kart or bike your creation will replace.
5. **Tune Your Vehicle**: set an in-game name (up to 10 UTF-16 code units) and adjust its stats. Numeric values can exceed the slider range; to use 2×, 3×, or 4×, multiply the displayed stock value and enter the result.
6. **Build & Install**: review the creations and destinations. The app finds Dolphin's own folders (`Load\Riivolution` and the SD card sync folder) and installs the mod there, so no root needs changing. You can also add another folder, such as a real Wii SD card. In Dolphin, right-click Mario Kart Wii, choose "Start with Riivolution Patches...", and set Custom Vehicle Garage to Enabled. Leave the SD Root as Dolphin shows it.

The in-game bars use `machine_para.bin`, a separate table of visual ratings; the game does not derive these bars from the gameplay values in `kartParam.bin`. The garage updates both: gameplay values in `kartParam.bin` and the matching visual ratings in all seven UI archives. A slider at its high end maps to a menu rating of 20; values entered beyond the slider range extend the rating beyond 20. Display ratings must fit the file's signed 16-bit field. The Off-Road control edits the standard off-road speed multiplier (KCL flag `0x03`).

Vehicle names are patched in language-specific UI message archives. The name field allows up to 10 UTF-16 code units so names fit the in-game label space; the exporter still checks each selected slot and reports its available limit rather than resizing game archives.

## Updates and releases

Use **Update** in the app to check GitHub for a newer release. If you agree, the Windows executable is downloaded, checked against GitHub's SHA-256 asset digest, replaced, and restarted. Save any edits first. Creations and game data stay in the app's data folder. Automatic replacement is available only in the packaged Windows app; source users should update their checkout instead.

GitHub Actions tests and builds pushes to `main`. Successful builds of the current `main` commit publish a Windows release with version `0.<workflow run>.<attempt>`; a later run receives a higher version. Pull requests are tested and built but not released. Pushing several commits together produces one build of the final commit, and a build superseded by a newer `main` commit is not published. Download the first update-capable executable from GitHub Releases; older builds cannot update themselves.

This checkout currently sits inside a parent repository. Its workflow runs on GitHub only after the committed `CustomVehicleGarage` subtree is pushed to the project's own `main` branch.

## Build the exe

```powershell
.\build_exe.ps1
```

## Without the window

```powershell
python -m vehiclegarage build --out "D:\sd" --disc "game.rvz" --dolphintool "C:\Dolphin\DolphinTool.exe"
```

## Not done yet

- The updated in-game stat bars still need a user check in Dolphin or on a Wii.
- No vehicle pictures, colours, or menu icons: the app only edits stats.
- Item hit-box and item immunity are not in `kartParam.bin`, so they are not editable yet.
