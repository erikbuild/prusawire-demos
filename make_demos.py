#!/usr/bin/env python3
# ABOUTME: Generates motion-only Prusawire CoreXZ demo G-code files.
# ABOUTME: Checks every move against a safe box and estimates run times.
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
    python3 make_demos.py --max-speed 400       # if you've raised your limits
    python3 make_demos.py --accel 4000          # if you've raised max_z_accel
    python3 make_demos.py --repeat 5            # showreel plays 5x back to back

Run `python3 make_demos.py -h` for all options.
"""

import argparse
import math
import os

# --------------------------------------------------------------------------
# Machine + safe envelope
# --------------------------------------------------------------------------
# Speed and acceleration limits come from --max-speed / --accel.
MACHINE = dict(square_corner_velocity=12.0)

SAFE = dict(x_min=15.0, x_max=235.0,
            y_min=20.0, y_max=190.0,
            z_min=25.0, z_max=170.0)


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
        self.warnings = []       # problems worth telling the user at generation time

    # -- helpers ----------------------------------------------------------
    def v(self, speed):
        """Clamp requested speed (mm/s) to --max-speed."""
        return min(speed, self.args.max_speed)

    def warn(self, text):
        self.warnings.append(text)

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

    def finish(self):
        a = self.args
        self.move(x=a.cx, y=a.cy, z=a.cz, speed=100)
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


def peak_speed(height, requested, args):
    """Top speed reached by a stroke of `height` mm that starts and ends
    at a reversal (near standstill): the lower of the requested speed,
    --max-speed, and sqrt(accel * height)."""
    return min(requested, args.max_speed, math.sqrt(args.accel * height))


def reversal_height(speed, args):
    """Shortest stroke, start to stop, that still reaches `speed` at --accel."""
    return speed * speed / args.accel


def demo_zigzag(g, args):
    """Tall zigzag across the gantry at rising speed, then full-speed reversals."""
    x0, x1 = SAFE["x_min"] + 5, SAFE["x_max"] - 5
    half = min(70.0, args.cz - SAFE["z_min"], SAFE["z_max"] - args.cz)
    zlo, zhi = args.cz - half, args.cz + half
    g.msg("Z zigzag - Z as fast as X")
    g.move(x=x0, z=zlo, speed=150)
    g.dwell(500)
    teeth = 8
    for spd in tiers(args):
        reached = peak_speed(zhi - zlo, spd, args)
        if reached < min(spd, args.max_speed) - 0.5:
            g.warn(f"Z zigzag tier {spd:.0f} mm/s only reaches {reached:.0f} mm/s: "
                   f"{zhi - zlo:.0f} mm teeth are too short at {args.accel:.0f} mm/s^2")
        g.msg(f"Z zigzag {reached:.0f} mm/s")
        for direction in (1, -1):
            xs = (x0, x1) if direction == 1 else (x1, x0)
            n = teeth * 2
            for i in range(1, n + 1):
                x = xs[0] + (xs[1] - xs[0]) * i / n
                z = zhi if i % 2 else zlo
                g.move(x=x, z=z, speed=spd)
        g.dwell(400)

    # Reversals: the shortest strokes that still reach top speed, sweeping X
    height = min(reversal_height(args.max_speed, args), zhi - zlo)
    g.msg(f"Top-speed reversals {peak_speed(height, args.max_speed, args):.0f} mm/s")
    g.move(x=x0, z=args.cz, speed=150)
    amp = height / 2
    n = 24
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
    ("05_helix_3d", "3D helix", demo_helix),
]


# --------------------------------------------------------------------------
# Time estimate (Klipper-style lookahead with junction deviation)
# --------------------------------------------------------------------------
def estimate_seconds(moves, args):
    m = dict(MACHINE, max_velocity=args.max_speed, max_accel=args.accel,
             max_z_velocity=args.max_speed, max_z_accel=args.accel)
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


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default="gcode", help="output folder (default: gcode)")
    p.add_argument("--max-speed", type=float, default=300.0,
                   help="cap for any requested speed, mm/s (default 300 = stock limit)")
    p.add_argument("--accel", type=float, default=2000.0,
                   help="machine acceleration, mm/s^2, for sizing strokes and "
                        "estimating times (default 2000 = stock max_z_accel)")
    p.add_argument("--speeds", type=float, nargs="+", default=[100, 200, 300],
                   help="speed tiers for zigzag/circles, mm/s (default 100 200 300)")
    p.add_argument("--helix-speed", type=float, default=150.0,
                   help="3D helix speed, mm/s - this one moves the bed (default 150)")
    p.add_argument("--home-cmd", default="CHOME",
                   help="homing command at the start (default CHOME = stock macro "
                        "that homes only when needed; use G28 to always home)")
    p.add_argument("--repeat", type=int, default=1, help="showreel passes per file")
    p.add_argument("--cx", type=float, default=125.0, help="centre X (default 125)")
    p.add_argument("--cy", type=float, default=105.0, help="bed Y during demos (default 105)")
    p.add_argument("--cz", type=float, default=97.5, help="centre Z (default 97.5)")
    return p.parse_args(argv)


def main():
    args = parse_args()
    os.makedirs(args.out, exist_ok=True)
    report = []
    warnings = []
    try:
        for slug, title, fn in DEMOS:
            g = build(fn, title, args)
            path = os.path.join(args.out, f"prusawire_{slug}.gcode")
            with open(path, "w") as f:
                f.write(g.text())
            report.append((os.path.basename(path), estimate_seconds(g.moves, args), len(g.lines)))
            warnings += [w for w in g.warnings if w not in warnings]
        g = build_showreel(args)
        path = os.path.join(args.out, "prusawire_00_showreel.gcode")
        with open(path, "w") as f:
            f.write(g.text())
        report.insert(0, (os.path.basename(path), estimate_seconds(g.moves, args), len(g.lines)))
        g = build_showreel(args, loop_hook=True)
        path = os.path.join(args.out, "prusawire_00_showreel_loop.gcode")
        with open(path, "w") as f:
            f.write(g.text())
        report.insert(1, (os.path.basename(path), estimate_seconds(g.moves, args), len(g.lines)))
    except OutOfBounds as e:
        raise SystemExit(f"Refusing to write: a move would leave the safe box ({e}). "
                         "Adjust --cx/--cz or the SAFE limits.")

    print(f"Wrote {len(report)} files to {args.out}/  (times are estimates at "
          f"{args.max_speed:.0f} mm/s, {args.accel:.0f} mm/s^2)")
    for name, secs, n in report:
        print(f"  {name:38s} ~{fmt_time(secs):>6s}   {n:5d} lines")
    for w in warnings:
        print(f"WARNING: {w}")


if __name__ == "__main__":
    main()
