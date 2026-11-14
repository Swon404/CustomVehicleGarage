---
name: riivolution-patch
description: Write and debug Riivolution wiidisc XML patches and the SD-card folder layout for Mario Kart Wii mods like CustomVehicleGarage. Use when generating or changing the mod's XML or the files it points to.
---

# Riivolution patches

## Reference

Use `ExampleMods/riivolution/FunnyVehiclesUSA.xml` as the template. It is read-only, so copy it rather than editing it.

## XML structure

```xml
<wiidisc version="1">
  <id game="RMCE"/>                       <!-- RMCE = US, RMCP = PAL, RMCJ = JPN, RMCK = KOR -->
  <options>
    <section name="..."><option name="..."><choice name="Enabled"><patch id="x"/></choice></option></section>
  </options>
  <patch id="x">
    <file disc="/rel/StaticR.rel" external="/Mod/StaticRU.rel" offset="" create="true"/>
    <file disc="main.dol" external="/Mod/mainU.dol" offset="" create="true"/>
    <file disc="/Race/Common.szs" external="/Mod/Common.szs" offset="" create="true"/>
    <memory valuefile="/Mod/codes/LoaderE.bin" offset="0x80258700"/>
    <memory offset="0x8000629C" value="48252FB0"/>
    <folder external="/Mod/codes/USA" disc="/codes" create="true"/>
  </patch>
</wiidisc>
```

- `disc` is the path inside the game disc. `external` is the path on the SD card, relative to the SD root.
- One `<file>` entry is needed for each changed archive or executable.
- Each region has its own `id` and its own `StaticR*.rel`, `main*.dol`, and `codes/<region>` files. Keep region builds separate.

## What CustomVehicleGarage generates

`export.riivolution_xml` emits one `<file disc="/<path>" external="/CustomVehicleGarage/<path>" resize="true" create="true"/>` per patched archive (`Race/Common.szs`, the seven `Scene/UI` parameter archives, and localized UI archives when a vehicle name changes). It adds no `<memory>` patches and does not touch `main.dol` or `StaticR.rel`: this mod changes stats and labels in the 36 stock slots. The `<id>` comes from the game ID read off the user's disc (first four characters).

## SD card layout

```
SD:/riivolution/CustomVehicleGarage.xml
SD:/CustomVehicleGarage/...        (files referenced by external=)
```

Dolphin uses the same layout under `%APPDATA%\Dolphin Emulator\Load\Riivolution\` (`riivolution\*.xml` and the mod folder side by side). Start the game from the game list with "Start with Riivolution Patches...".

## Rules

- Generate the XML from code. Don't hand-edit copies per slot.
- Keep the `<id>` matched to the disc region. Mismatched IDs won't apply.
- The `RegionPatch.bat` in `ExampleMods` applies `wstrt` to the Japanese build only. Don't reuse it for USA output.
- Check that every `external=` path exists before reporting a build as complete.
- In-game behaviour of mods built this way has not been confirmed in Dolphin or on a console. Say so when reporting results, unless it has since been tested.
