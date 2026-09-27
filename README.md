# Prusawire CoreXZ Demo Programs

Motion-only demo programs for showing off the Prusawire at 3DPrintopia. **Nothing heats and nothing extrudes.** The toolhead dances in the vertical X/Z plane that faces the audience, which is the plane CoreXZ is built for.

Made for the stock `prusawire-klipper-config` (Klipper, `kinematics: corexz`, 300 mm/s, 2000 mm/s², **Z limits the same as X**).

## Files

| File | ~Time | What it shows |
|---|---|---|
| `prusawire_00_showreel.gcode` | 5:00 | Demos 01–06 back to back, homes once |
| `prusawire_00_showreel_loop.gcode` | 5:00 | Same, but ends by calling `_DEMO_FILE_DONE` for hands-free looping (needs `prusawire_demo.cfg`) |
| `prusawire_01_z_zigzag.gcode` | 1:40 | 110 mm-tall zigzag across the whole gantry at 100, 200 and 300 mm/s, then a tight fast Z "buzz" |
| `prusawire_02_z_sprint.gcode` | 0:46 | Full-height Z sprints. Starts at **12 mm/s (MK3S leadscrew max)**, then 60, 150, 300 mm/s |
| `prusawire_03_one_motor_diamond.gcode` | 0:26 | Diamond (45° edges, **one motor per edge**) vs. square (both motors), then nested diamonds |
| `prusawire_04_vertical_curves.gcode` | 0:49 | Vertical circles at 3 speeds, spiral in/out, 3:2 Lissajous, five-point star |
| `prusawire_05_skywriter.gcode` | 0:42 | Traces P-R-U-S-A-W-I-R-E one letter at a time, each ~110 mm tall |
| `prusawire_06_helix_3d.gcode` | 0:32 | Gantry and bed together trace an 8-turn helix up and back down (150 mm/s) |

Times are estimates at stock limits. `preview.png` shows every path from the front.

## Running

1. **Clear the bed.** The nozzle stays at least 25 mm above it, but the gantry sweeps nearly the full width.
2. Upload the `.gcode` files through Mainsail and start any one as a normal print.
3. Each section title shows on the LCD / Mainsail status line (`M117`) so people can read what they're watching.

Every file starts with `CHOME` (the stock macro that homes only if needed). If your config doesn't have it, regenerate with `--home-cmd G28`.

### Looping all day (optional)

1. Copy `prusawire_demo.cfg` next to `printer.cfg` and add `[include prusawire_demo.cfg]`. Restart Klipper.
2. Upload `prusawire_00_showreel_loop.gcode`.
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
python3 make_demos.py --speeds 150 300 450        # zigzag / circle speed tiers
python3 make_demos.py --repeat 6                  # a ~30 min showreel with no macros needed
python3 make_demos.py --home-cmd G28              # always home at start
python3 check_and_preview.py                      # re-verify + redraw preview.png
```

**Light painting:** `--led toolhead` (Nitehawk) or `--led Stealthburner` (SB2209) turns the toolhead LEDs on while drawing and off while travelling. Combine it with `--sky-mode word` to write the whole word in one line, then shoot it with a phone on a 10–15 s night-mode or long exposure in a dim spot. Visitors get a photo of PRUSAWIRE written in light.

## Booth talking points

- **Why is Z so fast?** On an MK3S, Z runs on leadscrews and the firmware caps it at 12 mm/s and 200 mm/s². On the Prusawire, the gantry is lifted by the same two belts and motors that move X, so Z gets the same limits as X: 300 mm/s and 2000 mm/s² in the stock config. That's **25× the speed and 10× the acceleration.** Demo 02 starts at MK3S speed so people can see the difference.
- **Two motors, two axes.** In CoreXZ, motor A moves along X+Z and motor B along X−Z. A pure X or pure Z move turns *both* motors. A 45° diagonal turns only *one*. Watch the pulleys during demo 03: on the diamond, one motor is still on every edge.
- **What it's good for:** fast Z-hops and layer changes, Z-heavy vase and spiral work, and quick travel moves that clear the part.
- **Based on the Voron Switchwire,** built largely from MK3/MK4 leftovers. Open source from Positron 3D.
