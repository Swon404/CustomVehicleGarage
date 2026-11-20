# Custom Vehicle Garage for Mario Kart Wii

Design your own Mario Kart Wii vehicles on the PC and install them as a Riivolution mod. Creations replace the game's 36 stock vehicles, so you choose which stock vehicle each one takes over.

## Getting started

1. Run `CustomVehicleGarage.exe` (or `python -m vehiclegarage` from the source folder).
2. In **Setup**, select your own Mario Kart Wii disc image and Dolphin's `DolphinTool.exe`, then choose **Import Game Data**. Game files are not included with the app.
3. In **My Garage**, choose **Create Vehicle**, pick the stock kart or bike it will replace, give it a name, adjust its stats, and save it.
4. Open **Build & Install** and select either your garage or **OnnY's Custom Vehicles**. OnnY's collection replaces all 36 slots; use **View Examples** to explore it.
5. Choose **Build & Play in Dolphin**, or select a destination and choose **Build & Install Mod**. For a Wii, select the SD card as a destination and use Riivolution.

## Building and playing

To edit an OnnY preset without changing the built-in collection, choose **View Examples** and **Edit Garage Copy**. The app can install to Dolphin's `Load\Riivolution` and SD card sync folders, or to another folder such as a Wii SD card. **Build & Play in Dolphin** always installs to Dolphin's Riivolution folder as well as your selected destinations. On Windows, close any running Dolphin instances when prompted; Exit cancels Build & Play. `Dolphin.exe` must be beside the configured `DolphinTool.exe`.

Alternatively, in Dolphin, right-click Mario Kart Wii, choose "Start with Riivolution Patches...", and enable Custom Vehicle Garage. Leave the SD Root as Dolphin shows it.

Use **Cancel Build** to stop before installation and keep the previous mod at every destination. Once the final installation starts, cancellation is unavailable. Repeated builds reuse locally cached patched archives when the source and relevant changes are unchanged; the first build after changing stats or names still needs to compress the affected archives.

US (`RMCE01`), European (`RMCP01`), Japanese (`RMCJ01`) and Korean (`RMCK01`) game IDs are supported. Korean imports use the game's `_R` menu parameter archives and `_K` message archives; re-import any older Korean cache before building. Region handling has synthetic tests but has not been verified in-game for every region.

The in-game bars use `machine_para.bin`, a separate table of visual ratings; the game does not derive these bars from the gameplay values in `kartParam.bin`. The garage updates both: gameplay values in `kartParam.bin` and the matching visual ratings in all seven UI archives. A slider at its high end maps to a menu rating of 20; values entered beyond the slider range extend the rating beyond 20. Display ratings must fit the file's signed 16-bit field. The Off-Road control edits the standard off-road speed multiplier (KCL flag `0x03`).

Vehicle names are patched in language-specific UI message archives. Each slot and language has its own existing string space; the exporter checks it and reports when a name does not fit rather than resizing game archives. Each garage can opt in to **Shorten garage vehicle names** on the Build & Install page; the app reports shortened names without changing the saved creations. Longer names may also be clipped by the game even if they fit in the file; that has not been tested.

When tuning a vehicle, hover over a value for its description and stock range. Displayed values are rounded for readability; unchanged values retain their full precision. Advanced sliders use the imported stock vehicles' minimum and maximum values. When every stock value is identical, the range extends from zero to twice that value (or -1 to 1 if it is zero). Max normal acceleration uses 1–12. These are editing ranges, not safety limits: exact values outside them remain editable and are preserved until changed.

## Organising and sharing garages

The garage picker switches between independent collections. Switching does not change the installed mod: build and install again when ready. Each garage can hold multiple creations for a slot, but only one can be included in the mod at a time. Use **File Vehicle** to copy or move the selected creation to another garage; if that garage already has an included creation for the slot, the filed copy is excluded until you change it. **Manage Garages > Copy Onny's** makes an independent, editable copy of the full OnnY collection.

**Export Garage** saves a JSON file with vehicle names, stats, slot assignments, inclusion settings, name-fitting preference, and texture references/credits. **File Vehicle > Export vehicle** exports one creation. **Import** opens either file; a garage is imported as a new garage and a vehicle is added to the current garage. OnnY development JSON exports can also be imported as new garages. Name shortening is enabled for these OnnY imports and copies because their names may not fit every game's language files.

Transfer files do **not** contain texture archives or game data. On another PC, re-import any missing texture from its creator; the app warns if a referenced file is missing or fails its checksum. Re-importing the same texture should restore the saved reference. Check creators' terms before sharing their work.

Existing creations stay in their original data folder as **My Garage**. On first use, the app also copies existing creation JSON files to `garage-migration-backup` in its data folder; it does not overwrite that backup on later runs. Deleting a garage does not delete this backup or affect other garages or an already installed mod.

## Refining OnnY's Custom Vehicles

OnnY's Custom Vehicles includes 36 strong, challenging and silly builds, including Feather, which is extremely light and fast. Some values exceed the normal slider ranges and their in-game effects have not been verified. Choose **Manage Garages > Copy Onny's**, edit the resulting garage normally, and build that garage to test your changes. Previously saved development drafts are still used in development builds and included when copying OnnY's; they are not modified or deleted.

In a development build, select the garage and choose **Export > Export OnnY presets from this garage**. Include exactly one vehicle for each of the 36 stock slots; excluded alternatives are ignored. Presets do not support textures or non-editor stats, so remove these from included vehicles before export. Any unchanged performance values are filled from your imported game's stock data; import the game first if needed. The exported JSON contains names and stats, not game archives.

To incorporate an approved export into a future build, replace `vehiclegarage/assets/onny-presets.json` with that file and run the test suite. Exporting alone does not modify the bundled presets. Official releases ignore local drafts and do not show the preset export tool; **Edit Garage Copy** remains available.

## Community textures

The texture browser searches the [Custom Mario Kart vehicle texture category](https://mkwiiki.org/wiki/Category:Vehicle/Texture). Select a result to see its creator, source link and preview if available. The list and previews are cached locally; **Refresh** updates the list. "Match vehicle name" is enabled by default and searches titles, page content and the wiki's separate list of supported vehicles, including multi-vehicle entries. It suggests possible matches, not a compatibility guarantee; turn it off to browse everything.

Use **Download & Apply** for supported direct SZS/ZIP links. For other hosts, choose **Open Download**, save the creator's file, then choose **Import SZS / ZIP**. The first import opens Downloads; each file or folder picker remembers its own last location. Extract other archive formats yourself first. You can also import an SZS or ZIP without selecting a catalogue entry. The app checks archive structure and documented vehicle and character filenames; it cannot verify that a creator's file contents actually match the filename. Only race archives for the selected vehicle are installed; menu images and unrelated files in the download are not. Packs may affect only certain characters or multiplayer modes and can also change the included character model. Missing variants retain their original appearance.

Save the vehicle after importing, then build the mod. Imported files are kept in the app's local `textures` folder, independently of the disposable catalogue/preview cache. Community content is downloaded from its creator, not bundled with the app; check its terms and credit the creator. This feature still needs in-game testing.

## Updates and releases

Official release builds check GitHub when they start and show **Update** only if a newer release is available. If you agree, the Windows executable is downloaded, checked against GitHub's SHA-256 asset digest, replaced, and restarted. Save any edits first. Creations and game data stay in the app's data folder. Source, locally built and pull-request builds are labelled development builds and do not offer automatic updates, which could replace unpublished work with an older release. Versions with the previous broken updater need a one-time manual download of a newer executable from GitHub Releases.

Download the [latest Windows release](https://github.com/Swon404/CustomVehicleGarage/releases/latest/download/CustomVehicleGarage.exe). If your app does not show an update, download and run this executable manually; older builds cannot update themselves.

Updating the executable does not remove garage data. On Windows, the app stores it under `%APPDATA%\CustomVehicleGarage`; existing creations in its `creations` folder remain **My Garage**. If the garage looks empty, first check that you are using the same Windows account as before and that this folder still contains your creation files. On first startup with the newer garage system, those files are also backed up to `garage-migration-backup`.

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

The command-line build uses the currently selected garage and its name-fitting setting.

## Not done yet

- The updated in-game stat bars still need a user check in Dolphin or on a Wii.
- No live 3D preview or in-game menu icon replacement for texture packs.
- Item hit-box and item immunity are not in `kartParam.bin`, so they are not editable yet.
