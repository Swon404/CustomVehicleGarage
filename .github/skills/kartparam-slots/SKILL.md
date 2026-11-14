---
name: kartparam-slots
description: Edit Mario Kart Wii vehicle stats in kartParam.bin and assign custom creations to the 36 stock vehicle slots. Use when changing vehicle stats, mapping a creation to a slot, or debugging kartParam.bin.
---

# kartParam.bin and vehicle slots

## Format

- A 4-byte big-endian vehicle count (36 for the stock game), then 36 sections of 396 bytes each (99 words).
- File size must equal `4 + count * 396`. `vehiclegarage/kartparam.py` checks this.
- Words are 4 bytes at index × 4. Ints: `tires`, `drift_type`, `weight_class`, `mini_turbo_duration`. Everything else is a float.
- Speed and rotation multipliers are 32 floats each (one per KCL flag). Default speed multiplier is 1, default rotation is 0.7.
- Full field list: `FIELD_INDEX` in `vehiclegarage/kartparam.py`. The wiki table is the source of truth: https://mkwiiki.org/wiki/Vehicle_Statistics

## Slots

- The 36 sections are stock vehicles, ordered by vehicle ID. The game only reads these IDs, so custom creations overwrite a chosen stock slot.
- A slot assignment is `(stock vehicle ID) -> (creation stats)`. Keep the stock vehicle's model and name. Only the stats change.
- `kartParam.bin` also appears inside `Common.szs` and the seven UI archives (`MenuSingle`, `MenuMulti`, `MenuOther`, `Globe`, `Award`, `Event`, `Present`). Patch each copy from that archive's own base bytes.
- The menu stat bars are a separate visual table in `parameter/machine_para.bin`, not computed live from `kartParam.bin`. Its layout is 27×7 character and 36×7 vehicle signed big-endian int16 ratings. The seven categories are Speed, Weight, Acceleration, Handling, Drift, Off-Road, and Mini-Turbo. It appears in all seven UI archives.
- When changing slider-backed vehicle stats, update the corresponding `machine_para.bin` rating in every UI archive too. CustomVehicleGarage maps the 0–100 slider to the game's 0–20 menu rating scale and linearly extrapolates numeric values beyond the slider range; the result must fit the signed 16-bit field. The Off-Road bar controls `speed_multiplier_3` (standard KCL off-road flag `0x03`). Preserve character ratings and unedited vehicle ratings. This file affects menu presentation only; `kartParam.bin` controls gameplay.

## Editing rules

- Edit through `KartParam.from_bytes` and `Vehicle.set`. Do not patch offsets by hand.
- Keep unknown bytes unchanged. The `Vehicle` class stores raw bytes for this.
- Parse visual ratings through `MachinePara` in `vehiclegarage/machinepara.py`; do not hand-patch offsets.
- Validate ranges before writing (for example weight class in 0-2, tires in 0-3). Clamp or reject bad values; don't write them.
- Test each change: round trip, the changed field reads back, and no other field changed.
