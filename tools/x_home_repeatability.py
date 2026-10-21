#!/usr/bin/env python3
# ABOUTME: Measures sensorless homing on a CoreXZ printer through Moonraker: where X lands (from
# ABOUTME: motor step counts) and whether the gantry slips in Z (fixed-point probe or Z-map shift).
"""
Re-homes from Z120, Z60 and Z20 (three times each). After every home it parks at X125 Y105 Z10,
reads the motor step counts with GET_POSITION, and probes there.

    python3 tools/x_home_repeatability.py x out.csv      # G28 X only
    python3 tools/x_home_repeatability.py full out.csv   # cold-start G28 (forgets X and Y first)

The printer homes and probes, so clear the bed. Set MOONRAKER_URL when not running on the Pi,
e.g. MOONRAKER_URL=http://192.168.1.152:7125.
"""
import argparse
import csv
import json
import os
import re
import urllib.request

MOONRAKER = os.environ.get("MOONRAKER_URL", "http://localhost:7125")
HEIGHTS = [120, 60, 20] * 3
REF_X, REF_Y, REF_Z = 125.0, 105.0, 10.0   # nozzle; the probe sits 38.6 mm right, at X163.6
STOP_MM = 0.5
HOME_SCRIPTS = {
    "x": "G28 X",
    "full": "SET_KINEMATIC_POSITION CLEAR_HOMED=XY\nG28",
}


def request(path, body=None, timeout=180):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(MOONRAKER + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)["result"]


def gcode(script):
    request("/printer/gcode/script", {"script": script})


def config_settings():
    return request("/printer/objects/query?configfile=settings")["status"]["configfile"]["settings"]


def usteps_per_mm(settings):
    """Microsteps per mm of belt; CoreXZ motors A and B share stepper_x's drive settings."""
    s = settings["stepper_x"]
    return s["full_steps_per_rotation"] * s["microsteps"] / s["rotation_distance"]


def axis_shift(da, db):
    """Splits a count shift on motors A (stepper_x) and B (stepper_z) into X and Z shifts."""
    return (da + db) / 2, (da - db) / 2


def mcu_counts_from_store(store):
    """The motor step counts from the newest GET_POSITION response in a Moonraker gcode_store."""
    for entry in reversed(store):
        for line in entry["message"].splitlines():
            line = line.lstrip("/ ")
            if line.startswith("mcu:"):
                return {k: int(v) for k, v in re.findall(r"(\w+):(-?\d+)", line[4:])}
    raise RuntimeError("GET_POSITION mcu line not found")


def mcu_counts():
    gcode("M400\nGET_POSITION")
    return mcu_counts_from_store(request("/server/gcode_store?count=20")["gcode_store"])


def probe_z():
    gcode(f"G90\nG1 Z{REF_Z} F1200\nG1 X{REF_X} Y{REF_Y} F6000\nPROBE")
    z = request("/printer/objects/query?probe=last_z_result")["status"]["probe"]["last_z_result"]
    gcode(f"G90\nG1 Z{REF_Z} F1200\nG1 X{REF_X} Y{REF_Y} F6000")
    return z


def measure():
    z = probe_z()
    counts = mcu_counts()
    return z, counts["stepper_x"], counts["stepper_z"]


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Measure where sensorless homing lands on a CoreXZ.")
    p.add_argument("mode", choices=sorted(HOME_SCRIPTS),
                   help="x: G28 X only; full: cold-start G28 path")
    p.add_argument("csv_path", help="where to write the results")
    return p.parse_args(argv)


def main():
    args = parse_args()
    per_mm = usteps_per_mm(config_settings())
    print("Full G28 and baseline...", flush=True)
    gcode("BED_MESH_CLEAR\nG28\nG90")
    p0, a0, b0 = measure()
    rows = [{"run": 0, "start_z": "G28", "probe_z": p0, "steps_a": a0, "steps_b": b0,
             "x_shift_mm": 0.0, "z_map_shift_mm": 0.0, "probe_delta_mm": 0.0}]
    print(f"baseline: probe_z={p0:.4f}  A={a0}  B={b0}", flush=True)
    print(f"{'run':>3} {'startZ':>6} {'x_shift':>8} {'zmap':>7} {'probe_d':>8}", flush=True)

    for i, h in enumerate(HEIGHTS, start=1):
        gcode(f"G90\nG1 Z{h} F1200\nG1 X{REF_X} Y{REF_Y} F6000\n{HOME_SCRIPTS[args.mode]}\nG90")
        p, a, b = measure()
        x_us, z_us = axis_shift(a - a0, b - b0)
        row = {"run": i, "start_z": h, "probe_z": p, "steps_a": a, "steps_b": b,
               "x_shift_mm": x_us / per_mm,
               "z_map_shift_mm": z_us / per_mm,
               "probe_delta_mm": p - p0}
        rows.append(row)
        print(f"{i:>3} {h:>6} {row['x_shift_mm']:>8.3f} {row['z_map_shift_mm']:>7.3f} "
              f"{row['probe_delta_mm']:>8.4f}", flush=True)
        if abs(row["probe_delta_mm"]) > STOP_MM or abs(row["z_map_shift_mm"]) > STOP_MM:
            print(f"STOP: shift over {STOP_MM} mm; not re-homing.", flush=True)
            break

    with open(args.csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.csv_path}", flush=True)


if __name__ == "__main__":
    main()
