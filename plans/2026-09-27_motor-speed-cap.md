# Plan: cap CoreXZ motor speed, not just toolhead speed

Date: 2026-09-27

## Why

On a CoreXZ, motor A turns with X+Z and motor B with X−Z, so the faster motor runs at
|vx| + |vz|. A 45° move at 300 mm/s drives one motor at 424 mm/s. Klipper only limits
toolhead speed, so it allows this.

On enceladus (Einsy, 0.35 A, stealthChop), diagonals held at 250 mm/s (354 mm/s motor) and
stalled at 300 mm/s (424 mm/s motor). The gantry fell into the bed twice. Demo 03 (diamond),
04 (circles, Lissajous, star) and the 01 buzz all exceed 350 mm/s motor speed today.

## Changes

1. `--max-motor-speed` (default 300 mm/s): the fastest either motor may turn, as belt mm/s.
2. `allowed_speed(requested, dx, dz, d, args)`: the requested speed, capped by `--max-speed` and by
   `max_motor_speed * d / (|dx| + |dz|)`. `GcodeWriter.move()` uses it for every emitted F.
3. The zigzag labels and the buzz stroke height use the capped speed, so the LCD stays honest.
4. `check_and_preview.py --max-motor-speed` (default 300): independently checks that every move's
   motor speed, F × (|dx| + |dz|) / d, stays at or under the limit.
5. README: explain the motor limit and add `--max-motor-speed` to "Going faster".

## Tests

- Unit: `allowed_speed` for pure X, pure Z, 45° and shallow angles, and the `--max-speed` interaction.
- Integration: no move in any demo or the showreel exceeds the motor limit, and the labels match the capped speeds.
- End-to-end: the stock build passes the checker, and a build with `--max-motor-speed 450` fails the stock check.
