# Prusawire CoreXZ Demo Programs

Motion-only demo programs for showing off the Prusawire at 3DPrintopia. **Nothing heats and nothing extrudes.** The toolhead dances in the vertical X/Z plane that faces the audience, which is the plane CoreXZ is built for.

Made for the stock `prusawire-klipper-config` (Klipper, `kinematics: corexz`, 300 mm/s, 2000 mm/s², **Z limits the same as X**).

## Files

| File | ~Time | What it shows |
|---|---|---|
| `prusawire_00_showreel.gcode` | 5:15 | Demos 01–06 back to back, homes once |
| `prusawire_00_showreel_loop.gcode` | 5:15 | Same, but ends by calling `_DEMO_FILE_DONE` for hands-free looping (needs `prusawire_demo.cfg`) |
| `prusawire_01_z_zigzag.gcode` | 1:50 | 140 mm-tall zigzag across the whole gantry at 100, 200 and 300 mm/s, then top-speed reversals: the shortest strokes that still reach full speed |
| `prusawire_02_z_sprint.gcode` | 0:46 | Full-height Z sprints. Starts at **12 mm/s (MK3S leadscrew max)**, then 60, 150, 300 mm/s |
| `prusawire_03_one_motor_diamond.gcode` | 0:26 | Diamond (45° edges, **one motor per edge**) vs. square (both motors), then nested diamonds |
| `prusawire_04_vertical_curves.gcode` | 0:49 | Vertical circles at 3 speeds, spiral in/out, 3:2 Lissajous, five-point star |
| `prusawire_05_skywriter.gcode` | 0:42 | Traces P-R-U-S-A-W-I-R-E one letter at a time, each ~110 mm tall |
| `prusawire_06_helix_3d.gcode` | 0:32 | Gantry and bed together trace an 8-turn helix up and back down (150 mm/s) |

Times are estimates at stock limits. `preview.png` shows every path from the front.

## Quick install (on the Pi)

SSH into the printer's Pi, then:

```
git clone https://github.com/erikbuild/prusawire-demos.git
cd prusawire-demos
./install-demo.sh
```

The installer asks before each step (press Enter for yes):

1. Copy the demo `.gcode` files to `~/printer_data/gcodes/`, so they show up in Mainsail.
2. Copy `prusawire_demo.cfg` (the `DEMO_LOOP` macros) to `~/printer_data/config/`.
3. Add `[include prusawire_demo.cfg]` to the top of `printer.cfg`, after saving a timestamped backup. It skips this if the line is already there.

If step 2 or 3 changed anything, restart Klipper afterwards (`FIRMWARE_RESTART`). To update later, run `git pull` and then `./install-demo.sh` again. If your printer_data lives somewhere else, run `PRINTER_DATA=/path/to/printer_data ./install-demo.sh`.

## Running

1. **Clear the bed.** The nozzle stays at least 25 mm above it, but the gantry sweeps nearly the full width.
2. Start any `.gcode` file from Mainsail as a normal print. If you didn't use the installer, upload the files through Mainsail first.
3. Each section title shows on the LCD / Mainsail status line (`M117`) so people can read what they're watching.

Every file starts with `CHOME` (the stock macro that homes only if needed). If your config doesn't have it, regenerate with `--home-cmd G28`.

### Looping all day (optional)

1. Copy `prusawire_demo.cfg` next to `printer.cfg` and add `[include prusawire_demo.cfg]`. Restart Klipper. (Installer steps 2 and 3 do this.)
2. Upload `prusawire_00_showreel_loop.gcode`. (Installer step 1 does this.)
3. In the console, run `DEMO_LOOP` (optionally `DEMO_LOOP PAUSE=30` for 30 s between passes).
4. To stop, run `DEMO_STOP`, which lets the current pass finish, or `DEMO_STOP NOW=1`, which cancels immediately.

Mainsail's Cancel button also ends the loop mid-pass. Only if you cancel during the rest between passes does the timer still restart it, so use `DEMO_STOP` then.

Heads-up: the stock `CANCEL_PRINT` runs `PRINT_END`, which retracts 8 mm of filament (cold retracts are allowed because `min_extrude_temp: 0`). If filament is loaded, that's a cold pull. Either unload filament for the show or let passes finish with `DEMO_STOP`.

## Safety

- **Klipper enforces your limits.** Requested speeds above `max_velocity` / `max_z_velocity` just run at your limit, so these files can't push the machine beyond its config.
- The generator refuses to write any move outside the safe box: **X 15–235, Y 20–190, Z 25–170**. `check_and_preview.py` re-reads the finished G-code and checks this independently, along with making sure there are no heater or extrusion commands.
- The files end with motors still enabled, so the gantry holds position until Klipper's idle timeout.

## Customizing

```
python3 make_demos.py --text "3DPRINTOPIA"        # skywriter text (A–Z, 0–9, - ! space)
python3 make_demos.py --max-speed 400             # if you've tuned past 300 mm/s
python3 make_demos.py --accel 4000                # if you've raised max_z_accel
python3 make_demos.py --speeds 150 300 450        # zigzag / circle speed tiers
python3 make_demos.py --repeat 6                  # a ~30 min showreel with no macros needed
python3 make_demos.py --home-cmd G28              # always home at start
python3 check_and_preview.py                      # re-verify + redraw preview.png
python3 check_and_preview.py --max-speed 450      # same, for a raised-limit build
```

`check_and_preview.py` needs matplotlib. Set it up once with `python3 -m venv .venv && .venv/bin/pip install matplotlib`, then run the scripts and tests with `.venv/bin/python`.

### Going faster

The stock config caps Z at 300 mm/s and 2000 mm/s². G-code can't get past that (`SET_VELOCITY_LIMIT` doesn't touch `max_z_velocity` / `max_z_accel`), so going faster means raising the limits in `printer.cfg` first:

```
[printer]
max_velocity: 450
max_accel: 4000
max_z_velocity: 450
max_z_accel: 4000
```

Prove the new limits on the machine before a show: no skipped steps, no belt slap. Then regenerate with matching numbers and check the output against them:

```
python3 make_demos.py --max-speed 450 --accel 4000 --speeds 100 200 300 400 450
python3 check_and_preview.py --max-speed 450
```

Demo 01 labels each tier with the speed it will actually reach. A tooth is at most 140 mm tall, so the top possible speed is √(accel × 140): about 530 mm/s at 2000 mm/s² and 750 mm/s at 4000. If you ask for more than that, the generator prints a `WARNING` and labels the tier with its real speed.

### Tests

```
.venv/bin/python -m unittest discover -s tests
```

**Light painting:** `--led toolhead` (Nitehawk) or `--led Stealthburner` (SB2209) turns the toolhead LEDs on while drawing and off while travelling. Combine it with `--sky-mode word` to write the whole word in one line, then shoot it with a phone on a 10–15 s night-mode or long exposure in a dim spot. Visitors get a photo of PRUSAWIRE written in light.

## Booth talking points

- **Why is Z so fast?** On an MK3S, Z runs on leadscrews and the firmware caps it at 12 mm/s and 200 mm/s². On the Prusawire, the gantry is lifted by the same two belts and motors that move X, so Z gets the same limits as X: 300 mm/s and 2000 mm/s² in the stock config. That's **25× the speed and 10× the acceleration.** Demo 02 starts at MK3S speed so people can see the difference.
- **Two motors, two axes.** In CoreXZ, motor A moves along X+Z and motor B along X−Z. A pure X or pure Z move turns *both* motors. A 45° diagonal turns only *one*. Watch the pulleys during demo 03: on the diamond, one motor is still on every edge.
- **What it's good for:** fast Z-hops and layer changes, Z-heavy vase and spiral work, and quick travel moves that clear the part.
- **Based on the Voron Switchwire,** built largely from MK3/MK4 leftovers. Open source from Positron 3D.
