# Custom Vehicle Garage for Mario Kart Wii

Design your own Mario Kart Wii vehicles on the PC and install them as a Riivolution mod. Creations replace the game's 36 stock vehicles, so you choose which stock vehicle each one takes over.

## Use it

1. Run `dist\CustomVehicleGarage.exe` (or `python -m vehiclegarage`).
2. **Setup** (first run): pick your own Mario Kart Wii image (ISO, RVZ, WBFS...) and `DolphinTool.exe` (it comes with Dolphin), then import. You can browse for them or search a selected drive, starting with common locations; stop the search once you have found the files. Nothing from the game ships with this app.
3. **My Garage**: create a vehicle, search saved creations by name or weight class, edit them, or include/exclude them from the mod.
4. **Choose Vehicle**: pick the stock kart or bike your creation will replace. Cards show saved creations and whether they are included or excluded.
5. **Tune Your Vehicle**: enter the required in-game name and adjust its stats. Numeric values can exceed the slider range. Hover over a value for its description and stock range. Displayed values are rounded for readability; unchanged values retain their full precision. Optionally select **Browse Textures** to find a community appearance.
6. **Build & Install**: choose **My Garage** or **OnnY's Custom Vehicles**, then review the destinations. Use **View Examples** and **Edit Garage Copy** to create your own version of a preset; editing a copy does not change the built-in collection. The app finds Dolphin's own folders (`Load\Riivolution` and the SD card sync folder) and installs the mod there, so no root needs changing. You can also add another folder, such as a real Wii SD card. Choose **Build & Play in Dolphin** to build the selected collection and launch the game with the mod enabled; this always installs to Dolphin's Riivolution folder as well as your selected destinations. On Windows, close any running Dolphin instances when prompted before continuing; Exit cancels Build & Play without closing the garage. Dolphin.exe must be beside the configured DolphinTool.exe. Alternatively, in Dolphin, right-click Mario Kart Wii, choose "Start with Riivolution Patches...", and set Custom Vehicle Garage to Enabled. Leave the SD Root as Dolphin shows it.

Use **Cancel Build** to stop before installation and keep the previous mod at every destination. Once the final installation starts, cancellation is unavailable. Repeated builds reuse locally cached patched archives when the source and relevant changes are unchanged; the first build after changing stats or names still needs to compress the affected archives.

US (`RMCE01`), European (`RMCP01`), Japanese (`RMCJ01`) and Korean (`RMCK01`) game IDs are supported. Korean imports use the game's `_R` menu parameter archives and `_K` message archives; re-import any older Korean cache before building. Region handling has synthetic tests but has not been verified in-game for every region.

The in-game bars use `machine_para.bin`, a separate table of visual ratings; the game does not derive these bars from the gameplay values in `kartParam.bin`. The garage updates both: gameplay values in `kartParam.bin` and the matching visual ratings in all seven UI archives. A slider at its high end maps to a menu rating of 20; values entered beyond the slider range extend the rating beyond 20. Display ratings must fit the file's signed 16-bit field. The Off-Road control edits the standard off-road speed multiplier (KCL flag `0x03`).

Vehicle names are patched in language-specific UI message archives. Each slot and language has its own existing string space; the exporter checks it and reports when a name does not fit rather than resizing game archives. Longer names may also be clipped by the game even if they fit in the file; that has not been tested.

## Refining OnnY's Custom Vehicles

OnnY's Custom Vehicles includes 36 strong, challenging and silly builds, including Feather, which is light and fast. In a development build, open **Build & Install > View Examples**, select a vehicle, and choose **Edit Preset**. Saving updates a local draft, separate from My Garage. Select OnnY's Custom Vehicles when building to test the draft. The preset's stock slot is fixed, and this workflow edits names and stats only, not textures.

Choose **Export JSON** in the examples window to save the complete 36-vehicle collection. To incorporate an approved export into a future build, replace `vehiclegarage/assets/onny-presets.json` with that file and run the test suite. Exports contain preset names and stats, not game data. Official release builds ignore local drafts and do not show the development editing or export controls; **Edit Garage Copy** remains available.

## Community textures

The texture browser searches the [Custom Mario Kart vehicle texture category](https://mkwiiki.org/wiki/Category:Vehicle/Texture). Select a result to see its creator, source link and preview if available. The list and previews are cached locally; **Refresh** updates the list. "Match vehicle name" is enabled by default and searches titles, page content and the wiki's separate list of supported vehicles, including multi-vehicle entries. It suggests possible matches, not a compatibility guarantee; turn it off to browse everything.

Use **Download & Apply** for supported direct SZS/ZIP links. For other hosts, choose **Open Download**, save the creator's file, then choose **Import SZS / ZIP**. The first import opens Downloads; each file or folder picker remembers its own last location. Extract other archive formats yourself first. You can also import an SZS or ZIP without selecting a catalogue entry. The app checks archive structure and documented vehicle and character filenames; it cannot verify that a creator's file contents actually match the filename. Only race archives for the selected vehicle are installed; menu images and unrelated files in the download are not. Packs may affect only certain characters or multiplayer modes and can also change the included character model. Missing variants retain their original appearance.

Save the vehicle after importing, then build the mod. Imported files are kept in the app's local `textures` folder, independently of the disposable catalogue/preview cache. Community content is downloaded from its creator, not bundled with the app; check its terms and credit the creator. This feature still needs in-game testing.

## Updates and releases

Official release builds check GitHub when they start and show **Update** only if a newer release is available. If you agree, the Windows executable is downloaded, checked against GitHub's SHA-256 asset digest, replaced, and restarted. Save any edits first. Creations and game data stay in the app's data folder. Source, locally built and pull-request builds are labelled development builds and do not offer automatic updates, which could replace unpublished work with an older release. Versions with the previous broken updater need a one-time manual download of a newer executable from GitHub Releases.

GitHub Actions tests and builds pushes to `main`. Successful builds of the current `main` commit publish a Windows release with version `0.<workflow run>.<attempt>`; a later run receives a higher version. Pull requests are tested and built but not released. Pushing several commits together produces one build of the final commit, and a build superseded by a newer `main` commit is not published. Download the first update-capable executable from GitHub Releases; older builds cannot update themselves.

## Credits

Created by **Swon404 and OnnY**. Thanks to the [Dolphin](https://dolphin-emu.org/) team, the [Custom Mario Kart Wiiki](https://mkwiiki.org/) community, and the individual texture creators credited in the browser. Community texture content belongs to its respective creators; check their terms before reusing or distributing it. The executable includes Python and other runtime components with their own [licence notices](https://docs.python.org/3/license.html). Mario Kart Wii is a Nintendo game; this project is not affiliated with Nintendo.

The former unlock setup option is no longer included. Removing it does not undo cheats or save changes previously made in Dolphin.

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
