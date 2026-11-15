# Custom Vehicle Garage

Design your own Mario Kart Wii vehicles on the PC and install them as a Riivolution mod. Creations replace the game's 36 stock vehicles, so you choose which stock vehicle each one takes over.

## Use it

1. Run `dist\CustomVehicleGarage.exe` (or `python -m vehiclegarage`).
2. **Setup** (first run): pick your own Mario Kart Wii image (ISO, RVZ, WBFS...) and `DolphinTool.exe` (it comes with Dolphin), then import. Nothing from the game ships with this app.
3. **My Garage**: create a vehicle, search saved creations by name or weight class, edit them, or include/exclude them from the mod.
4. **Choose Vehicle**: pick the stock kart or bike your creation will replace.
5. **Tune Your Vehicle**: set an in-game name (up to 10 UTF-16 code units) and adjust its stats. Numeric values can exceed the slider range; to use 2×, 3×, or 4×, multiply the displayed stock value and enter the result. Optionally select **Browse Textures** to find a community appearance.
6. **Build & Install**: review the creations and destinations. The app finds Dolphin's own folders (`Load\Riivolution` and the SD card sync folder) and installs the mod there, so no root needs changing. You can also add another folder, such as a real Wii SD card. Choose **Build & Play in Dolphin** to build the latest creations and launch the game with the mod enabled; this always installs to Dolphin's Riivolution folder as well as your selected destinations. Dolphin.exe must be beside the configured DolphinTool.exe. Alternatively, in Dolphin, right-click Mario Kart Wii, choose "Start with Riivolution Patches...", and set Custom Vehicle Garage to Enabled. Leave the SD Root as Dolphin shows it.

Use **Cancel Build** to stop before installation and keep the previous mod at every destination. Once the final installation starts, cancellation is unavailable. Repeated builds reuse locally cached patched archives when the source and relevant changes are unchanged; the first build after changing stats or names still needs to compress the affected archives.

US (`RMCE01`), European (`RMCP01`), Japanese (`RMCJ01`) and Korean (`RMCK01`) game IDs are supported. Korean imports use the game's `_R` menu parameter archives and `_K` message archives; re-import any older Korean cache before building. Region handling has synthetic tests but has not been verified in-game for every region.

The in-game bars use `machine_para.bin`, a separate table of visual ratings; the game does not derive these bars from the gameplay values in `kartParam.bin`. The garage updates both: gameplay values in `kartParam.bin` and the matching visual ratings in all seven UI archives. A slider at its high end maps to a menu rating of 20; values entered beyond the slider range extend the rating beyond 20. Display ratings must fit the file's signed 16-bit field. The Off-Road control edits the standard off-road speed multiplier (KCL flag `0x03`).

Vehicle names are patched in language-specific UI message archives. The name field allows up to 10 UTF-16 code units so names fit the in-game label space; the exporter still checks each selected slot and reports its available limit rather than resizing game archives.

## Community textures

The texture browser searches the [Custom Mario Kart vehicle texture category](https://mkwiiki.org/wiki/Category:Vehicle/Texture). Select a result to see its creator and preview if available. The list and previews are cached locally; **Refresh** updates the list. "Match vehicle name" is a text filter, not a compatibility guarantee.

Use **Download & Apply** for supported direct SZS/ZIP links. For other hosts, choose **Open Download**, save the creator's file, then choose **Import SZS / ZIP**. Extract other archive formats yourself first. You can also import an SZS or ZIP without selecting a catalogue entry. The app checks archive structure and documented vehicle and character filenames; it cannot verify that a creator's file contents actually match the filename. Only race archives for the selected vehicle are installed; menu images and unrelated files in the download are not. Packs may affect only certain characters or multiplayer modes and can also change the included character model. Missing variants retain their original appearance.

Save the vehicle after importing, then build the mod. Imported files are kept in the app's local `textures` folder, independently of the disposable catalogue/preview cache. Community content is downloaded from its creator, not bundled with the app; check its terms and credit the creator. This feature still needs in-game testing.

## Updates and releases

Use **Update** in the app to check GitHub for a newer release. If you agree, the Windows executable is downloaded, checked against GitHub's SHA-256 asset digest, replaced, and restarted. Save any edits first. Creations and game data stay in the app's data folder. Automatic replacement is available only in the packaged Windows app; source users should update their checkout instead.

GitHub Actions tests and builds pushes to `main`. Successful builds of the current `main` commit publish a Windows release with version `0.<workflow run>.<attempt>`; a later run receives a higher version. Pull requests are tested and built but not released. Pushing several commits together produces one build of the final commit, and a build superseded by a newer `main` commit is not published. Download the first update-capable executable from GitHub Releases; older builds cannot update themselves.

## Unlock characters, vehicles and courses in Dolphin

On **Build & Install**, choose **Set Up Character & Vehicle Unlock**. Close Dolphin and back up your Wii save first. After confirmation, the app downloads and verifies [Wiimm's License Unlock code](https://mkwiiki.org/wiki/License_Unlock) for the imported game's region and adds it to Dolphin's game-specific settings. It enables cheats for that game, so any other enabled codes for it can also run. Existing game settings are backed up when changed; the save itself is not backed up by the app. A revision-specific GameINI must be configured manually in Dolphin instead.

Start the game in Dolphin. At the licence selection screen, hold **Plus + Minus + 1 + B** on controller 1 and press the D-pad direction of the licence to unlock. The original instructions specify a Wii Remote rotated 45 degrees counterclockwise. The game sound briefly speeds up on success. Complete a race or change a Mii to save the unlocks permanently. This unlocks drivers, vehicles and courses for that licence, without changing trophies. The button configures Dolphin; it does not add a Gecko handler to the Riivolution files for a real Wii. The interaction with Dolphin's Riivolution launch and in-game activation still needs testing.

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
- No live 3D preview or in-game menu icon replacement for texture packs.
- Item hit-box and item immunity are not in `kartParam.bin`, so they are not editable yet.
