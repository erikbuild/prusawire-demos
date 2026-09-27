# Plan: README quick install + install-demo.sh

Date: 2026-09-27

## Goal

Run it on the Pi: `git clone`, then `./install-demo.sh`. The script asks before each
of these steps (default YES):

1. Copy `gcode/*.gcode` to `~/printer_data/gcodes/`.
2. Copy `prusawire_demo.cfg` to `~/printer_data/config/`.
3. Add `[include prusawire_demo.cfg]` to `~/printer_data/config/printer.cfg`, if it's not already there.

At the end, if step 2 or 3 changed anything, it reminds Erik to restart Klipper.

## Design

- `PRINTER_DATA` env var overrides `~/printer_data`. This covers non-standard
  installs, and the tests use it.
- Prompt `[Y/n]`: an empty answer, `y` or `yes` means yes (case-insensitive). EOF counts as the default.
- Step 1 overwrites files that are already there and says how many it copied.
  It errors if the gcodes folder is missing.
- Step 3:
  - Backs up `printer.cfg` to `printer.cfg.bak-<timestamp>` first.
  - Puts the include line at the **top** of the file, so it can never land inside
    Klipper's `#*# SAVE_CONFIG` block at the end.
  - Skips with a message if the line is already there (it's safe to re-run).
  - Skips if `prusawire_demo.cfg` isn't in the config folder, because that include would stop Klipper from starting.
  - Errors if `printer.cfg` is missing.
- Exit status is non-zero if any accepted step failed.
- Works with plain bash (no bash-4-only syntax), so it can also be tested on macOS.

## Tests

End-to-end tests, in `tests/test_install_script.py`, run the real script against a temp `PRINTER_DATA`:
all yes, all no, idempotent include, include at top and ahead of SAVE_CONFIG,
backup created, include skipped when the cfg is missing, missing printer.cfg or
gcodes folder reported, and the restart reminder shown only when needed.
The script is bash, so there are no separate unit tests. Its behaviour is exercised as a whole.

## README

Add a "Quick install (on the Pi)" section at the top of "Running":
`git clone https://github.com/erikbuild/prusawire-demos.git`, `cd`, `./install-demo.sh`.
