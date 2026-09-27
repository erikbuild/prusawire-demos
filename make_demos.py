#!/usr/bin/env python3
"""
Prusawire motion demos - G-code generator
=========================================

Generates motion-only (no heating, no extrusion) demo programs that show off
what CoreXZ kinematics make possible: the Z axis is driven by the same two belts
and motors as X, so Z can move as fast as X.

Target: Prusawire (Positron 3D) running Klipper with the stock
prusawire-klipper-config:
    kinematics: corexz
    max_velocity: 300     max_accel: 2000
    max_z_velocity: 300   max_z_accel: 2000
    X 0..250   Y 0..210 (bed)   Z 0..183

Safety by design
----------------
* Klipper clamps every move to the limits in printer.cfg, so these files can
  never move faster than your config allows. Requested speeds above your limits
  simply run at your limits.
* Every move is checked against a safe box (defaults below) before it is
  written, and generation fails if any move would leave it.
* The nozzle never goes below SAFE Z_MIN (default 25 mm) so the bed stays clear.
* Nothing heats and nothing extrudes.

Usage
-----
    python3 make_demos.py                       # writes ./gcode/*.gcode
    python3 make_demos.py --text "3DPRINTOPIA"  # change the skywriter text
    python3 make_demos.py --max-speed 400       # if you've raised your limits
    python3 make_demos.py --led toolhead        # light painting with the SB LEDs
    python3 make_demos.py --repeat 5            # showreel plays 5x back to back

Run `python3 make_demos.py -h` for all options.
"""

import argparse
import math
import os

# --------------------------------------------------------------------------
# Machine + safe envelope
# --------------------------------------------------------------------------
MACHINE = dict(max_velocity=300.0, max_accel=2000.0,
               max_z_velocity=300.0, max_z_accel=2000.0,
               square_corner_velocity=12.0)

SAFE = dict(x_min=15.0, x_max=235.0,
            y_min=20.0, y_max=190.0,
            z_min=25.0, z_max=170.0)

# Single-stroke font (Hershey "futural"), baseline at y=-9, cap height y=12.
# Each entry: (advance width, "x,y,x,y,... x,y,..." strokes separated by spaces)
FONT = {
    'A': (18, "9,12,1,-9 9,12,17,-9 4,-2,14,-2"),
    'B': (21, "4,12,4,-9 4,12,13,12,16,11,17,10,18,8,18,6,17,4,16,3,13,2 4,2,13,2,16,1,17,0,18,-2,18,-5,17,-7,16,-8,13,-9,4,-9"),
    'C': (21, "18,7,17,9,15,11,13,12,9,12,7,11,5,9,4,7,3,4,3,-1,4,-4,5,-6,7,-8,9,-9,13,-9,15,-8,17,-6,18,-4"),
    'D': (21, "4,12,4,-9 4,12,11,12,14,11,16,9,17,7,18,4,18,-1,17,-4,16,-6,14,-8,11,-9,4,-9"),
    'E': (19, "4,12,4,-9 4,12,17,12 4,2,12,2 4,-9,17,-9"),
    'F': (18, "4,12,4,-9 4,12,17,12 4,2,12,2"),
    'G': (21, "18,7,17,9,15,11,13,12,9,12,7,11,5,9,4,7,3,4,3,-1,4,-4,5,-6,7,-8,9,-9,13,-9,15,-8,17,-6,18,-4,18,-1 13,-1,18,-1"),
    'H': (22, "4,12,4,-9 18,12,18,-9 4,2,18,2"),
    'I': (8, "4,12,4,-9"),
    'J': (16, "12,12,12,-4,11,-7,10,-8,8,-9,6,-9,4,-8,3,-7,2,-4,2,-2"),
    'K': (21, "4,12,4,-9 18,12,4,-2 9,3,18,-9"),
    'L': (17, "4,12,4,-9 4,-9,16,-9"),
    'M': (24, "4,12,4,-9 4,12,12,-9 20,12,12,-9 20,12,20,-9"),
    'N': (22, "4,12,4,-9 4,12,18,-9 18,12,18,-9"),
    'O': (22, "9,12,7,11,5,9,4,7,3,4,3,-1,4,-4,5,-6,7,-8,9,-9,13,-9,15,-8,17,-6,18,-4,19,-1,19,4,18,7,17,9,15,11,13,12,9,12"),
    'P': (21, "4,12,4,-9 4,12,13,12,16,11,17,10,18,8,18,5,17,3,16,2,13,1,4,1"),
    'Q': (22, "9,12,7,11,5,9,4,7,3,4,3,-1,4,-4,5,-6,7,-8,9,-9,13,-9,15,-8,17,-6,18,-4,19,-1,19,4,18,7,17,9,15,11,13,12,9,12 12,-5,18,-11"),
    'R': (21, "4,12,4,-9 4,12,13,12,16,11,17,10,18,8,18,6,17,4,16,3,13,2,4,2 11,2,18,-9"),
    'S': (20, "17,9,15,11,12,12,8,12,5,11,3,9,3,7,4,5,5,4,7,3,13,1,15,0,16,-1,17,-3,17,-6,15,-8,12,-9,8,-9,5,-8,3,-6"),
    'T': (16, "8,12,8,-9 1,12,15,12"),
    'U': (22, "4,12,4,-3,5,-6,7,-8,10,-9,12,-9,15,-8,17,-6,18,-3,18,12"),
    'V': (18, "1,12,9,-9 17,12,9,-9"),
    'W': (24, "2,12,7,-9 12,12,7,-9 12,12,17,-9 22,12,17,-9"),
    'X': (20, "3,12,17,-9 17,12,3,-9"),
    'Y': (18, "1,12,9,2,9,-9 17,12,9,2"),
    'Z': (20, "17,12,3,-9 3,12,17,12 3,-9,17,-9"),
    '0': (20, "9,12,6,11,4,8,3,3,3,0,4,-5,6,-8,9,-9,11,-9,14,-8,16,-5,17,0,17,3,16,8,14,11,11,12,9,12"),
    '1': (20, "6,8,8,9,11,12,11,-9"),
    '2': (20, "4,7,4,8,5,10,6,11,8,12,12,12,14,11,15,10,16,8,16,6,15,4,13,1,3,-9,17,-9"),
    '3': (20, "5,12,16,12,10,4,13,4,15,3,16,2,17,-1,17,-3,16,-6,14,-8,11,-9,8,-9,5,-8,4,-7,3,-5"),
    '4': (20, "13,12,3,-2,18,-2 13,12,13,-9"),
    '5': (20, "15,12,5,12,4,3,5,4,8,5,11,5,14,4,16,2,17,-1,17,-3,16,-6,14,-8,11,-9,8,-9,5,-8,4,-7,3,-5"),
    '6': (20, "16,9,15,11,12,12,10,12,7,11,5,8,4,3,4,-2,5,-6,7,-8,10,-9,11,-9,14,-8,16,-6,17,-3,17,-2,16,1,14,3,11,4,10,4,7,3,5,1,4,-2"),
    '7': (20, "17,12,7,-9 3,12,17,12"),
    '8': (20, "8,12,5,11,4,9,4,7,5,5,7,4,11,3,14,2,16,0,17,-2,17,-5,16,-7,15,-8,12,-9,8,-9,5,-8,4,-7,3,-5,3,-2,4,0,6,2,9,3,13,4,15,5,16,7,16,9,15,11,12,12,8,12"),
    '9': (20, "16,5,15,2,13,0,10,-1,9,-1,6,0,4,2,3,5,3,6,4,9,6,11,9,12,10,12,13,11,15,9,16,5,16,0,15,-5,13,-8,10,-9,8,-9,5,-8,4,-6"),
    '-': (18, "4,1,14,1"),
    '!': (10, "5,12,5,-2 5,-7,4,-8,5,-9,6,-8,5,-7"),
    ' ': (12, ""),
}


# --------------------------------------------------------------------------
# G-code writer
# --------------------------------------------------------------------------
class OutOfBounds(Exception):
    pass


class GcodeWriter:
    def __init__(self, args):
        self.args = args
        self.lines = []
        self.pos = None          # (x, y, z) once known
        self.moves = []          # (x0,y0,z0,x1,y1,z1,v) for estimates/previews
        self.markers = []        # (move_index, label) section markers

    # -- helpers ----------------------------------------------------------
    def v(self, speed):
        """Clamp requested speed (mm/s) to --max-speed."""
        return min(speed, self.args.max_speed)

    def raw(self, text):
        self.lines.append(text)

    def comment(self, text=""):
        self.lines.append(f"; {text}" if text else ";")

    def msg(self, text):
        # M117 shows on the LCD / Mainsail status line; RESPOND logs to console
        self.lines.append(f"M117 {text}")
        self.lines.append(f"RESPOND MSG=\"{text}\"")
        self.markers.append((len(self.moves), text))

    def dwell(self, ms):
        self.lines.append(f"G4 P{int(ms)}")
        self.moves.append(("dwell", ms / 1000.0))

    def led(self, on):
        if not self.args.led:
            return
        level = 1.0 if on else 0.0
        self.lines.append(
            f"SET_LED LED={self.args.led} RED={level} GREEN={level} BLUE={level}")

    def check(self, x, y, z):
        s = SAFE
        eps = 1e-6
        if not (s["x_min"] - eps <= x <= s["x_max"] + eps):
            raise OutOfBounds(f"X={x:.2f} outside {s['x_min']}..{s['x_max']}")
        if not (s["y_min"] - eps <= y <= s["y_max"] + eps):
            raise OutOfBounds(f"Y={y:.2f} outside {s['y_min']}..{s['y_max']}")
        if not (s["z_min"] - eps <= z <= s["z_max"] + eps):
            raise OutOfBounds(f"Z={z:.2f} outside {s['z_min']}..{s['z_max']}")

    def move(self, x=None, y=None, z=None, speed=100.0):
        if self.pos is None:
            raise RuntimeError("position unknown - call start() first")
        x0, y0, z0 = self.pos
        x = x0 if x is None else x
        y = y0 if y is None else y
        z = z0 if z is None else z
        self.check(x, y, z)
        if abs(x - x0) < 1e-4 and abs(y - y0) < 1e-4 and abs(z - z0) < 1e-4:
            return
        spd = self.v(speed)
        parts = ["G1"]
        if abs(x - x0) >= 1e-4:
            parts.append(f"X{x:.3f}")
        if abs(y - y0) >= 1e-4:
            parts.append(f"Y{y:.3f}")
        if abs(z - z0) >= 1e-4:
            parts.append(f"Z{z:.3f}")
        parts.append(f"F{spd * 60:.0f}")
        self.lines.append(" ".join(parts))
        self.moves.append((x0, y0, z0, x, y, z, spd))
        self.pos = (x, y, z)

    def polyline(self, pts, speed, y=None):
        """pts: iterable of (x, z) in the vertical plane facing the audience."""
        for (px, pz) in pts:
            self.move(x=px, z=pz, y=y, speed=speed)

    # -- program framing ----------------------------------------------------
    def start(self, title):
        a = self.args
        self.comment("=" * 70)
        self.comment(f"Prusawire CoreXZ demo: {title}")
        self.comment("Motion only - no heating, no extrusion. Generated by make_demos.py")
        self.comment(f"Safe box: X {SAFE['x_min']}-{SAFE['x_max']}  "
                     f"Y {SAFE['y_min']}-{SAFE['y_max']}  Z {SAFE['z_min']}-{SAFE['z_max']}")
        self.comment(f"Requested speeds capped at {a.max_speed:.0f} mm/s; "
                     "Klipper further clamps to printer.cfg limits.")
        self.comment("Clear the bed before running!")
        self.comment("=" * 70)
        self.raw("M107                ; part fan off (nothing to cool)")
        self.raw(f"{a.home_cmd}               ; home (stock macro homes only if needed)")
        self.raw("G90                 ; absolute positioning")
        self.raw("G21                 ; millimetres")
        # First move out of home goes UP first, then over. We don't know
        # where the toolhead is after homing, so emit it without tracking.
        self.raw(f"G1 Z{a.cz:.3f} F{min(60, a.max_speed) * 60:.0f}   ; lift to demo height")
        self.raw(f"G1 X{a.cx:.3f} Y{a.cy:.3f} F{min(150, a.max_speed) * 60:.0f}  ; centre")
        self.pos = (a.cx, a.cy, a.cz)
        self.led(False)

    def finish(self):
        a = self.args
        self.move(x=a.cx, y=a.cy, z=a.cz, speed=100)
        self.led(False)
        self.raw("M400")
        self.msg("Prusawire - CoreXZ")
        self.comment("end of demo - motors stay enabled so the gantry holds position")

    def text(self):
        return "\n".join(self.lines) + "\n"


# --------------------------------------------------------------------------
# Demo building blocks. All patterns are drawn in the X/Z plane, i.e. the
# vertical plane facing the audience. Y is the bed and mostly stays put.
# --------------------------------------------------------------------------
def tiers(args):
    return [s for s in args.speeds if s <= args.max_speed] or [args.max_speed]


def demo_zigzag(g, args):
    """Wide zigzag across the gantry at rising speed, then a fast 'buzz'."""
    x0, x1 = SAFE["x_min"] + 5, SAFE["x_max"] - 5
    zlo, zhi = args.cz - 55, args.cz + 55
    g.msg("Z zigzag - Z as fast as X")
    g.move(x=x0, z=zlo, speed=150)
    g.dwell(500)
    teeth = 8
    for spd in tiers(args):
        g.msg(f"Z zigzag {spd:.0f} mm/s")
        for direction in (1, -1):
            xs = (x0, x1) if direction == 1 else (x1, x0)
            n = teeth * 2
            for i in range(1, n + 1):
                x = xs[0] + (xs[1] - xs[0]) * i / n
                z = zhi if i % 2 else zlo
                g.move(x=x, z=z, speed=spd)
        g.dwell(400)

    # Buzz: short, tight, very fast Z reversals while sweeping X
    g.msg("Z buzz - rapid reversals")
    g.move(x=x0, z=args.cz, speed=150)
    amp = 8
    n = 60
    for direction in (1, -1):
        xs = (x0, x1) if direction == 1 else (x1, x0)
        for i in range(1, n + 1):
            x = xs[0] + (xs[1] - xs[0]) * i / n
            z = args.cz + (amp if i % 2 else -amp)
            g.move(x=x, z=z, speed=args.max_speed)
    g.move(x=args.cx, z=args.cz, speed=150)
    g.dwell(400)


def demo_z_sprint(g, args):
    """Full-height vertical sprints, starting at MK3S leadscrew speed."""
    lo, hi = SAFE["z_min"] + 2, SAFE["z_max"] - 2
    g.move(x=args.cx, z=lo, speed=100)
    g.dwell(600)
    sprint_speeds = [12] + [s for s in (60, 150) if s < args.max_speed] + [args.max_speed]
    for spd in sprint_speeds:
        label = f"Z sprint {spd:.0f} mm/s"
        if spd == 12:
            label += " (MK3S leadscrew max)"
        g.msg(label)
        reps = 1 if spd <= 12 else 2
        for _ in range(reps):
            g.move(z=hi, speed=spd)
            g.dwell(150)
            g.move(z=lo, speed=spd)
            g.dwell(150)
        g.dwell(500)
    g.move(z=args.cz, speed=150)


def demo_one_motor(g, args):
    """45-degree moves in XZ turn only ONE motor; axis moves turn both."""
    cx, cz = args.cx, args.cz
    r = 65
    spd = args.max_speed
    diamond = [(cx + r, cz), (cx, cz + r), (cx - r, cz), (cx, cz - r), (cx + r, cz)]
    square = [(cx + r, cz + r), (cx - r, cz + r), (cx - r, cz - r), (cx + r, cz - r), (cx + r, cz + r)]
    square = [(x, max(min(z, SAFE["z_max"]), SAFE["z_min"])) for x, z in square]

    g.msg("Diamond - each edge uses ONE motor")
    g.move(x=diamond[0][0], z=diamond[0][1], speed=150)
    g.dwell(400)
    for _ in range(3):
        g.polyline(diamond[1:], spd)
    g.dwell(500)

    g.msg("Square - each edge uses BOTH motors")
    g.move(x=square[0][0], z=square[0][1], speed=150)
    g.dwell(400)
    for _ in range(3):
        g.polyline(square[1:], spd)
    g.dwell(500)

    g.msg("Nested diamonds")
    for rr in (60, 45, 30, 15, 30, 45, 60):
        pts = [(cx + rr, cz), (cx, cz + rr), (cx - rr, cz), (cx, cz - rr), (cx + rr, cz)]
        g.move(x=pts[0][0], z=pts[0][1], speed=spd)
        g.polyline(pts[1:], spd)
    g.move(x=cx, z=cz, speed=150)
    g.dwell(400)


def circle_pts(cx, cz, r, start=0.0, turns=1.0, seg_deg=3.0, ccw=True):
    n = max(8, int(abs(turns) * 360 / seg_deg))
    sgn = 1 if ccw else -1
    for i in range(1, n + 1):
        a = start + sgn * 2 * math.pi * turns * i / n
        yield cx + r * math.cos(a), cz + r * math.sin(a)


def demo_curves(g, args):
    cx, cz = args.cx, args.cz
    top = args.max_speed

    g.msg("Vertical circles")
    r = 60
    g.move(x=cx + r, z=cz, speed=150)
    for spd in tiers(args):
        g.polyline(circle_pts(cx, cz, r, turns=2), spd)
    g.dwell(400)

    g.msg("Spiral in and out")
    n = 720
    turns = 6
    for i in range(1, n + 1):
        t = i / n
        rr = 60 - 50 * t
        a = 2 * math.pi * turns * t
        g.move(x=cx + rr * math.cos(a), z=cz + rr * math.sin(a), speed=top * 0.7)
    for i in range(1, n + 1):
        t = i / n
        rr = 10 + 50 * t
        a = 2 * math.pi * turns * (1 - t)
        g.move(x=cx + rr * math.cos(a), z=cz + rr * math.sin(a), speed=top * 0.7)
    g.dwell(400)

    g.msg("Lissajous 3:2")
    ax, az = 100, 62
    n = 600
    def liss(t):
        return cx + ax * math.sin(3 * t + math.pi / 2), cz + az * math.sin(2 * t)
    sx, sz = liss(0)
    g.move(x=sx, z=sz, speed=150)
    for _ in range(2):
        g.polyline((liss(2 * math.pi * i / n) for i in range(1, n + 1)), top)
    g.dwell(400)

    g.msg("Five-point star")
    R = 65
    star = []
    for k in range(6):
        a = math.pi / 2 + k * 4 * math.pi / 5
        star.append((cx + R * math.cos(a), cz + R * math.sin(a)))
    g.move(x=star[0][0], z=star[0][1], speed=150)
    for _ in range(3):
        g.polyline(star[1:], top)
    g.move(x=cx, z=cz, speed=150)
    g.dwell(400)


def layout_text(text, width, cap_height):
    """Return list of strokes [(x,z)...] in font units scaled to fit."""
    text = text.upper()
    missing = sorted({c for c in text if c not in FONT})
    if missing:
        raise SystemExit(f"Skywriter font has no glyphs for: {' '.join(missing)}")
    total = sum(FONT[c][0] for c in text)
    scale = min(width / total, cap_height / 21.0)
    strokes, cursor = [], 0.0
    for c in text:
        adv, enc = FONT[c]
        for st in enc.split():
            nums = [float(v) for v in st.split(",")]
            pts = [((cursor + nums[i]) * scale, (nums[i + 1] + 9) * scale)
                   for i in range(0, len(nums), 2)]
            strokes.append(pts)
        cursor += adv
    return strokes, total * scale, 21 * scale


def _draw_strokes(g, args, strokes, ox, oz):
    draw = min(args.draw_speed, args.max_speed)
    for st in strokes:
        pts = [(ox + x, oz + z) for x, z in st]
        g.led(False)
        g.move(x=pts[0][0], z=pts[0][1], speed=args.max_speed)
        g.led(True)
        g.polyline(pts[1:], draw)
    g.led(False)


def demo_skywriter(g, args):
    text = args.text.upper()
    g.msg(f"Skywriter: {text}")
    if args.sky_mode == "word":
        # Whole word in one line - small, but perfect for a long-exposure photo
        width = SAFE["x_max"] - SAFE["x_min"] - 10
        strokes, w, h = layout_text(text, width, cap_height=70)
        _draw_strokes(g, args, strokes, args.cx - w / 2, args.cz - h / 2)
    else:
        # One big letter at a time, ~110 mm tall, traced in the same spot
        for ch in text:
            if ch == " ":
                g.dwell(500)
                continue
            strokes, w, h = layout_text(ch, 200, cap_height=110)
            g.msg(f"Skywriter: {text}  [{ch}]")
            _draw_strokes(g, args, strokes, args.cx - w / 2, args.cz - h / 2)
            g.dwell(700)
    g.move(x=args.cx, z=args.cz, speed=150)
    g.dwell(600)


def demo_helix(g, args):
    """Toolhead + bed together: a fast helix, like a vase-mode travel."""
    cx, cy = args.cx, args.cy
    r = 45
    zlo, zhi = SAFE["z_min"] + 5, SAFE["z_max"] - 5
    turns = 8
    spd = min(args.helix_speed, args.max_speed)
    g.msg("3D helix - bed + gantry")
    g.move(x=cx + r, y=cy, z=zlo, speed=150)
    g.dwell(400)
    n = int(turns * 360 / 4)
    for leg in range(2):
        for i in range(1, n + 1):
            t = i / n
            a = 2 * math.pi * turns * t
            z = zlo + (zhi - zlo) * (t if leg == 0 else 1 - t)
            g.move(x=cx + r * math.cos(a), y=cy + r * math.sin(a), z=z, speed=spd)
    g.move(x=cx, y=cy, z=args.cz, speed=150)
    g.dwell(400)


DEMOS = [
    ("01_z_zigzag", "Z zigzag", demo_zigzag),
    ("02_z_sprint", "Z sprint vs MK3S", demo_z_sprint),
    ("03_one_motor_diamond", "One-motor diamond", demo_one_motor),
    ("04_vertical_curves", "Vertical curves", demo_curves),
    ("05_skywriter", "Skywriter", demo_skywriter),
    ("06_helix_3d", "3D helix", demo_helix),
]


# --------------------------------------------------------------------------
# Time estimate (Klipper-style lookahead with junction deviation)
# --------------------------------------------------------------------------
def estimate_seconds(moves):
    m = MACHINE
    jd_base = m["square_corner_velocity"] ** 2 * (math.sqrt(2) - 1)
    total = 0.0
    segs = []

    def flush(segs):
        if not segs:
            return 0.0
        # backward pass
        n = len(segs)
        end_v2 = 0.0
        for i in range(n - 1, -1, -1):
            s = segs[i]
            s["end_v2"] = end_v2
            s["start_v2"] = min(s["max_start_v2"], end_v2 + 2 * s["a"] * s["d"])
            end_v2 = s["start_v2"]
        # forward pass
        t = 0.0
        v2 = 0.0
        for s in segs:
            start_v2 = min(v2, s["start_v2"])
            end_v2 = min(s["end_v2"], start_v2 + 2 * s["a"] * s["d"])
            cruise_v2 = min(s["cruise_v2"],
                            (2 * s["a"] * s["d"] + start_v2 + end_v2) / 2)
            vs, ve, vc = math.sqrt(start_v2), math.sqrt(end_v2), math.sqrt(cruise_v2)
            a = s["a"]
            d_acc = (cruise_v2 - start_v2) / (2 * a)
            d_dec = (cruise_v2 - end_v2) / (2 * a)
            d_cru = max(0.0, s["d"] - d_acc - d_dec)
            t += (vc - vs) / a + (vc - ve) / a + (d_cru / vc if vc > 0 else 0)
            v2 = end_v2
        return t

    prev = None
    for mv in moves:
        if mv[0] == "dwell":
            total += flush(segs)
            segs, prev = [], None
            total += mv[1]
            continue
        x0, y0, z0, x1, y1, z1, v = mv
        dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        if d <= 0:
            continue
        v = min(v, m["max_velocity"])
        a = m["max_accel"]
        if abs(dz) > 1e-9:
            v = min(v, m["max_z_velocity"] * d / abs(dz))
            a = min(a, m["max_z_accel"] * d / abs(dz))
        u = (dx / d, dy / d, dz / d)
        s = dict(d=d, a=a, cruise_v2=v * v, u=u, jd=jd_base / a)
        s["centripetal"] = 0.0
        if prev is None:
            s["max_start_v2"] = 0.0
        else:
            cos_t = -(u[0] * prev["u"][0] + u[1] * prev["u"][1] + u[2] * prev["u"][2])
            cos_t = max(-0.999999, cos_t)
            if cos_t > 0.999999:
                s["max_start_v2"] = 0.0
            else:
                sin_d2 = math.sqrt(0.5 * (1 - cos_t))
                r_jd = sin_d2 / (1 - sin_d2) if sin_d2 < 1 else 1e9
                tan_d2 = sin_d2 / math.sqrt(0.5 * (1 + cos_t))
                cent = 0.5 * d * tan_d2 * a
                prev_cent = 0.5 * prev["d"] * tan_d2 * prev["a"]
                s["max_start_v2"] = min(r_jd * s["jd"] * a,
                                        r_jd * prev["jd"] * prev["a"],
                                        cent, prev_cent,
                                        s["cruise_v2"], prev["cruise_v2"])
        segs.append(s)
        prev = s
    total += flush(segs)
    return total


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def build(demo_fn, title, args):
    g = GcodeWriter(args)
    g.start(title)
    demo_fn(g, args)
    g.finish()
    return g


def build_showreel(args, loop_hook=False):
    g = GcodeWriter(args)
    g.start("Showreel (all demos)" + (" - loop version for DEMO_LOOP" if loop_hook else ""))
    for rep in range(args.repeat):
        if args.repeat > 1:
            g.comment(f"---- showreel pass {rep + 1} of {args.repeat} ----")
        for _, title, fn in DEMOS:
            g.comment(f"---- {title} ----")
            fn(g, args)
            g.dwell(1500)
    g.finish()
    if loop_hook:
        g.raw("_DEMO_FILE_DONE     ; tells prusawire_demo.cfg to relaunch (DEMO_LOOP)")
    return g


def fmt_time(s):
    m, s = divmod(int(round(s)), 60)
    return f"{m}:{s:02d}"


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="gcode", help="output folder (default: gcode)")
    p.add_argument("--max-speed", type=float, default=300.0,
                   help="cap for any requested speed, mm/s (default 300 = stock limit)")
    p.add_argument("--speeds", type=float, nargs="+", default=[100, 200, 300],
                   help="speed tiers for zigzag/circles, mm/s (default 100 200 300)")
    p.add_argument("--draw-speed", type=float, default=120.0,
                   help="skywriter drawing speed, mm/s (default 120)")
    p.add_argument("--helix-speed", type=float, default=150.0,
                   help="3D helix speed, mm/s - this one moves the bed (default 150)")
    p.add_argument("--text", default="PRUSAWIRE", help="skywriter text (A-Z 0-9 - ! space)")
    p.add_argument("--sky-mode", choices=["letters", "word"], default="letters",
                   help="skywriter: 'letters' = one big letter at a time (readable "
                        "from the aisle), 'word' = whole word small (for light painting)")
    p.add_argument("--led", default="",
                   help="neopixel name for light painting, e.g. 'toolhead' (Nitehawk) "
                        "or 'Stealthburner' (SB2209). Off by default.")
    p.add_argument("--home-cmd", default="CHOME",
                   help="homing command at the start (default CHOME = stock macro "
                        "that homes only when needed; use G28 to always home)")
    p.add_argument("--repeat", type=int, default=1, help="showreel passes per file")
    p.add_argument("--cx", type=float, default=125.0, help="centre X (default 125)")
    p.add_argument("--cy", type=float, default=105.0, help="bed Y during demos (default 105)")
    p.add_argument("--cz", type=float, default=97.5, help="centre Z (default 97.5)")
    args = p.parse_args()

    os.makedirs(args.out, exist_ok=True)
    report = []
    try:
        for slug, title, fn in DEMOS:
            g = build(fn, title, args)
            path = os.path.join(args.out, f"prusawire_{slug}.gcode")
            with open(path, "w") as f:
                f.write(g.text())
            report.append((os.path.basename(path), estimate_seconds(g.moves), len(g.lines)))
        g = build_showreel(args)
        path = os.path.join(args.out, "prusawire_00_showreel.gcode")
        with open(path, "w") as f:
            f.write(g.text())
        report.insert(0, (os.path.basename(path), estimate_seconds(g.moves), len(g.lines)))
        g = build_showreel(args, loop_hook=True)
        path = os.path.join(args.out, "prusawire_00_showreel_loop.gcode")
        with open(path, "w") as f:
            f.write(g.text())
        report.insert(1, (os.path.basename(path), estimate_seconds(g.moves), len(g.lines)))
    except OutOfBounds as e:
        raise SystemExit(f"Refusing to write: a move would leave the safe box ({e}). "
                         "Adjust --cx/--cz or the SAFE limits.")

    print(f"Wrote {len(report)} files to {args.out}/  (times are estimates at stock limits)")
    for name, secs, n in report:
        print(f"  {name:38s} ~{fmt_time(secs):>6s}   {n:5d} lines")


if __name__ == "__main__":
    main()
