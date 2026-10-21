#!/usr/bin/env python3
# ABOUTME: Runs each stage of a CoreXZ cold-start G28 on its own and measures per-motor step loss,
# ABOUTME: using a fixed-point probe for Z and a plain G28 X for X, then splitting into A/B cycles.
"""
Five reps of each stage, starting from Z120. After every stage it probes at X125 Y105, runs a
plain G28 X, and probes again, so a slip shows up as whole electrical cycles on motor A or B.

    python3 tools/homing_stage_slips.py cold-path out.csv  # G28 Z, travel to centre, G28 Y, full G28
    python3 tools/homing_stage_slips.py margin out.csv     # both motors at homing current: hold, back off

The printer homes and probes, so clear the bed. Set MOONRAKER_URL when not running on the Pi.
"""
import argparse
import csv

from x_home_repeatability import (REF_X, REF_Y, axis_shift, config_settings, gcode, measure,
                                  usteps_per_mm)

START_Z = 120
CHECK_Z = 20
REPS = 5
STOP_MM = 2
COLD_PATH_STAGES = {
    "z": "G28 Z",
    "xy": "G1 X1 Y-28 F3000\nG0 X125 Y105 F7800",
    "y": "G28 Y",
    "full": "SET_KINEMATIC_POSITION CLEAR_HOMED=XY\nG28",
}


def usteps_per_cycle(settings):
    """Microsteps per electrical cycle (4 full steps); a skipping motor slips whole cycles."""
    return 4 * settings["stepper_x"]["microsteps"]


def motor_cycles(x_us, z_us, per_cycle):
    """Turns X and Z shifts in microsteps back into motor A and B shifts in electrical cycles."""
    return (x_us + z_us) / per_cycle, (x_us - z_us) / per_cycle


def margin_stages(settings):
    """Both CoreXZ motors at _HOME_X's homing current: holding still, then backing off 5 mm."""
    run_a = settings["tmc2130 stepper_x"]["run_current"]
    run_b = settings["tmc2130 stepper_z"]["run_current"]
    divisor = float(settings["gcode_macro _home_x"]["variable_home_current_divisor"])
    low = (f"SET_TMC_CURRENT STEPPER=stepper_x CURRENT={run_a / divisor}\n"
           f"SET_TMC_CURRENT STEPPER=stepper_z CURRENT={run_b / divisor}")
    restore = (f"SET_TMC_CURRENT STEPPER=stepper_x CURRENT={run_a}\n"
               f"SET_TMC_CURRENT STEPPER=stepper_z CURRENT={run_b}")
    return {
        "hold": f"{low}\nG4 P10000\n{restore}",
        "backoff": f"{low}\nG91\nG1 X5 F1200\nG4 P250\n{restore}",
    }


STAGE_SETS = {"cold-path": lambda settings: COLD_PATH_STAGES, "margin": margin_stages}


def check_x():
    gcode(f"G90\nG1 Z{CHECK_Z} F1200\nG1 X{REF_X} Y{REF_Y} F6000\nG28 X\nG90")
    return measure()


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="Measure per-motor step loss in each homing stage.")
    p.add_argument("stage_set", choices=sorted(STAGE_SETS),
                   help="cold-path: each stage of a cold G28; margin: low-current hold and back-off")
    p.add_argument("csv_path", help="where to write the results")
    return p.parse_args(argv)


def main():
    args = parse_args()
    settings = config_settings()
    per_mm = usteps_per_mm(settings)
    per_cycle = usteps_per_cycle(settings)
    stop_usteps = STOP_MM * per_mm
    stages = STAGE_SETS[args.stage_set](settings)
    for stage, script in stages.items():
        print(f"[{stage}]\n{script}\n", flush=True)
    print("Setup: G28, then G28 X check...", flush=True)
    gcode("BED_MESH_CLEAR\nG28\nG90")
    measure()
    p_ref, a0, b0 = check_x()
    p0 = p_ref
    print(f"baseline: probe_z={p_ref:.4f} A={a0} B={b0}", flush=True)
    print(f"{'rep':>3} {'stage':>5} {'x_us':>5} {'z_us':>5} {'A_cyc':>6} {'B_cyc':>6} {'zcheck':>7}",
          flush=True)

    rows = []
    for rep in range(1, REPS + 1):
        for stage, script in stages.items():
            gcode(f"G90\nG1 Z{START_Z} F1200\nG1 X{REF_X} Y{REF_Y} F6000\n{script}\nG90")
            p1, a1, b1 = measure()
            p2, a2, b2 = check_x()
            # Both parts are count shifts at the same physical point; + Z means the gantry dropped.
            x_us, z_map_us = axis_shift(a2 - a0, b2 - b0)
            z_us = z_map_us + (p2 - p0) * per_mm
            a_cycles, b_cycles = motor_cycles(x_us, z_us, per_cycle)
            row = {"rep": rep, "stage": stage, "x_usteps": x_us, "z_usteps": z_us,
                   "a_cycles": a_cycles, "b_cycles": b_cycles,
                   "zcheck_usteps": (p2 - p1) * per_mm,
                   "probe_after_stage": p1, "probe_after_check": p2,
                   "steps_a": a2, "steps_b": b2}
            rows.append(row)
            print(f"{rep:>3} {stage:>5} {x_us:>5.0f} {z_us:>5.0f} {a_cycles:>6.2f} "
                  f"{b_cycles:>6.2f} {row['zcheck_usteps']:>7.1f}", flush=True)
            p0, a0, b0 = p2, a2, b2
            if (abs(x_us) > stop_usteps or abs(z_us) > stop_usteps
                    or abs(p2 - p_ref) * per_mm > stop_usteps):
                print(f"STOP: slip over {STOP_MM} mm; not re-homing.", flush=True)
                break
        else:
            continue
        break

    with open(args.csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {args.csv_path}", flush=True)


if __name__ == "__main__":
    main()
