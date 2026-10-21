# Plan: homing measurement tools in `tools/`

Date: 2026-10-20

## Why

On 2026-10-18 two scripts measured sensorless homing on enceladus through Moonraker. They found
one 3-cycle motor-B slip in about 10 full G28s. They lived in a session scratchpad. Erik will
tune driver_SGT next and wants a before/after benchmark, so the scripts move into this repo.

## Changes

1. `tools/x_home_repeatability.py {x|full} out.csv`: re-homes from Z120/60/20 (3×) and reports
   the X shift, the Z-map shift and the probe delta at X125 Y105 Z10 after each home.
2. `tools/homing_stage_slips.py {cold-path|margin} out.csv`: runs each stage of a cold G28, or
   both CoreXZ motors at homing current, then splits any slip into motor A/B electrical cycles.
3. The scripts take two things from the printer instead of hard-coding them:
   - The Moonraker URL, from `MOONRAKER_URL`, default `http://localhost:7125`. This lets them run
     on the Pi like `install-demo.sh`, and matches its `PRINTER_DATA=` style.
   - Steps per mm and µsteps per electrical cycle, from `[stepper_x]` in the configfile
     settings. Enceladus uses rotation_distance 32 (100 µsteps/mm); upstream's 40 gives 80.
4. Pure helpers, so the math is testable offline:
   - `mcu_counts_from_store(store)`: the newest `GET_POSITION` mcu counts in a gcode_store.
   - `axis_shift(da, db)`: CoreXZ count shifts to X and Z, (dA+dB)/2 and (dA−dB)/2.
   - `usteps_per_mm(settings)` and `usteps_per_cycle(settings)`.
   - `motor_cycles(x, z, per_cycle)`: back to motor A/B cycles.
   - `margin_stages(settings)`: builds the low-current scripts with unrounded currents.
5. README: a short "Homing measurement tools" section: what each tool does, how to run it,
   that it homes and probes, and the bed must be clear.

## Tests

- Unit: parsing real `GET_POSITION` output (newest wins, missing raises), `axis_shift`, the
  steps math for rotation_distance 32 and 40, and `motor_cycles`. That includes the real
  2026-10-18 slip: −192 µsteps on B only is 0 cycles on A and −3 on B.
- Integration: `margin_stages` with enceladus's real settings gives run/3 currents, unrounded.
- End-to-end: skipped; Erik authorized it on 2026-10-20. It would need several minutes of
  homing and probing on the printer.
