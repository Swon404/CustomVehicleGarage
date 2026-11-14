---
name: szs-archives
description: Read and patch Mario Kart Wii SZS/U8 archives (Common.szs, MenuSingle.szs, etc.) with the app's own yaz0.py and u8.py. Use when changing how CustomVehicleGarage edits game archives.
---

# Working with SZS archives

An `.szs` file is a Yaz0-compressed U8 archive. CustomVehicleGarage handles both itself, with no external tools.

## Code

- `vehiclegarage/yaz0.py`: `decompress(bytes)` and `compress(bytes, progress=None)`. The encoder is greedy with a hash chain; `Common.szs` takes about 3 seconds and comes out about 2.5% larger than Nintendo's. Output decodes to the exact input.
- `vehiclegarage/u8.py`: `find_files` maps every path to `(offset, size)`. Paths have the leading `./` directory removed. `read_file` and `replace_file` use those offsets. `replace_file` requires the same size, which is what makes in-place patching safe: no node table, name table or alignment changes.

## Where `kartParam.bin` lives

| Disc path | Path inside the archive |
| --- | --- |
| `Race/Common.szs` | `kartParam.bin` |
| `Scene/UI/MenuSingle.szs` | `parameter/kartParam.bin` |
| `Scene/UI/MenuMulti.szs` | `parameter/kartParam.bin` |
| `Scene/UI/Globe.szs` | `parameter/kartParam.bin` |
| `Scene/UI/Award.szs` | `parameter/kartParam.bin` |
| `Scene/UI/Event.szs` | `parameter/kartParam.bin` |
| `Scene/UI/MenuOther.szs` | `parameter/kartParam.bin` |
| `Scene/UI/Present.szs` | `parameter/kartParam.bin` |

All seven UI archives also contain `parameter/machine_para.bin`, the separate table of displayed stat-bar ratings. `vehiclegarage/export.py` updates it alongside `kartParam.bin` and leaves unchanged rows intact. The UI copies can differ from `Common.szs`, so patch each archive from its own stock bytes.

Localized `Scene/UI/*_<language>.szs` archives contain `message/Common.bmg`, which includes vehicle-name messages. `vehiclegarage/bmg.py` replaces the selected slot's message IDs in place, preserving the BMG and U8 file sizes; reject a name that will not fit the existing string allocation.

## Reading the disc

`DolphinTool.exe extract -i <image> -o <dir> -p DATA -s Race/Common.szs` writes `<dir>/DATA/files/Race/Common.szs` in under a second from an RVZ. `DolphinTool.exe header -i <image> -j` prints the game ID. Never call it with `-s sys/...`; only `files/` paths work.

## Rules

- Never write into `ExampleMods/` or the game's original archives. Work on copies.
- If a change needs files added, removed, or resized inside an archive, write a real U8 packer with tests first. In-place replacement cannot do it.
- Add tests with a synthetic U8 (see `build_u8` in `tests/test_archives.py`), never with game data.
