# Plan: Z zigzag goes faster (Option 3)

Date: 2026-09-27

## Goal

1. **Stock limits (300 mm/s, 2000 mm/s²):** make demo 01 actually hit its top speed
   everywhere it claims to, and make the finale show off acceleration honestly.
2. **Raised limits:** once Erik raises `max_velocity` / `max_z_velocity` /
   `max_z_accel` in `printer.cfg`, one regenerate command adds faster zigzag
   tiers that really reach their labelled speed.

## Facts that shape the design

- Klipper caps the Z component of every move at `max_z_velocity` / `max_z_accel`.
  `SET_VELOCITY_LIMIT` can't raise these, so G-code alone can't beat 300 mm/s Z on stock config.
- On a reversal (tooth tip), the toolhead nearly stops. For a stroke of Z height `h`
  at Z accel `a`, the peak Z speed is about `sqrt(a * h)`.
  - Zigzag teeth today: h = 110 mm → peak ≈ 469 mm/s. Reaches 300 on stock limits.
  - Buzz today: h = 16 mm → peak ≈ 179 mm/s. It never reaches the 300 it requests.
  - At 2000 mm/s², a 500 mm/s tier needs h ≥ 125 mm. The safe box allows up to 145 mm.
- `estimate_seconds` and `check_and_preview.py` hardcode 300 mm/s / 2000 mm/s², so
  both are wrong or fail once the limits are raised.

## Changes

1. **`--accel` flag** (default 2000, the stock `max_z_accel`). Tells the generator
   what acceleration the machine has. It's used to size strokes, label speeds and
   estimate times. The estimator takes its limits from `--max-speed` / `--accel`
   instead of the fixed `MACHINE` dict.
2. **Reachable-speed helper** `peak_speed(stroke_height, requested, args)`:
   `min(requested, max_speed, sqrt(accel * h))`.
3. **Zigzag tiers:**
   - Tooth height grows to the full safe Z range (±70 around `cz`, clamped to the box).
   - Each tier's LCD label shows the speed it will actually reach.
   - The generator prints a warning if a requested tier can't be reached with the
     available height, instead of silently mislabelling it.
4. **Finale ("Z buzz" → "Top-speed reversals"):** the stroke height is the
   shortest one that still reaches the top speed (`h = v² / a`, 45 mm at stock
   limits). This packs in as many full-speed reversals per second as the limits allow.
5. **`check_and_preview.py`:** add `--max-speed` (default 300) so the independent
   check validates raised-limit builds. The preview colour scale follows it.
6. **README:** add a "Going faster" section with the `printer.cfg` changes and the
   matching command, e.g.
   `python3 make_demos.py --max-speed 450 --accel 4000 --speeds 100 200 300 400 450`,
   and note that the limits should be proven on the machine first.

## Tests (stdlib `unittest`, no new deps for the generator)

- Unit: `peak_speed` values; buzz stroke sizing; estimator honours `--accel`.
- Integration: build demo 01 with stock and raised args, then check the labels
  match the reachable speeds, every move stays inside `SAFE`, and the warning is
  emitted for an unreachable tier.
- End-to-end: run `make_demos.py` CLI into a temp dir, then run
  `check_and_preview.py --max-speed …` on the output. This needs matplotlib,
  so it goes in a project `.venv`.

## Out of scope (loop back later)

- Other demos that "don't work". Erik will describe them after this change.

## Queued tasks (after this change)

- README: quick install steps (`git clone https://github.com/...` then run).
- `install-demo.sh`: installs the demo files onto the printer.
- Loop back on the other demos that "don't work".
