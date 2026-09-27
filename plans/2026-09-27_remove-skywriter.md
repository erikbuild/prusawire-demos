# Plan: remove the skywriter demo

Date: 2026-09-27

Erik: the skywriter doesn't work and looks bad. Remove it.

- `make_demos.py`: remove `FONT`, `layout_text`, `_draw_strokes`, `demo_skywriter`, its `DEMOS`
  entry, and the `--text`, `--sky-mode` and `--draw-speed` options.
- Remove `--led` / `GcodeWriter.led()`. They only lit the toolhead while the skywriter drew, so
  without it they'd do nothing.
- Renumber the helix from 06 to 05 (`prusawire_05_helix_3d.gcode`).
- `check_and_preview.py`: drop the skywriter title note and hide unused preview panels.
- README: drop the skywriter row, the `--text` example and the light-painting paragraph, and update the showreel time.
- Delete `gcode/prusawire_05_skywriter.gcode` and regenerate.
- Tests first: no skywriter in `DEMOS`, the CLI rejects `--text`/`--led`, and the generated folder has no skywriter file.
