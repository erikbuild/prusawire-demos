#!/usr/bin/env python3
# ABOUTME: Independently re-checks generated demo G-code for safety and speed limits.
# ABOUTME: Also renders preview.png, a front view of every demo path.
"""Re-parse generated G-code files: verify safety and render front-view previews."""
import argparse, glob, os, re, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

BOX = dict(X=(15, 235), Y=(20, 190), Z=(25, 170))
FORBIDDEN = re.compile(r"^(M10[49]|M1[49]0|M190|M141|M191|SET_HEATER)", re.I)
problems = []
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("folder", nargs="?", default="gcode", help="folder of .gcode files (default: gcode)")
ap.add_argument("--max-speed", type=float, default=300.0,
                help="highest allowed requested speed, mm/s (default 300 = stock limit)")
args = ap.parse_args()
limit = args.max_speed
files = sorted(glob.glob(args.folder + "/*.gcode"))
paths = {}
for fn in files:
    pos = {}
    segs, speeds, ys = [], [], []
    maxf = 0
    for ln, line in enumerate(open(fn), 1):
        code = line.split(";")[0].strip()
        if not code:
            continue
        if FORBIDDEN.match(code):
            problems.append(f"{fn}:{ln} heater command: {code}")
        if re.match(r"^G[01]\b", code):
            words = dict((w[0].upper(), float(w[1:])) for w in code.split()[1:])
            if "E" in words:
                problems.append(f"{fn}:{ln} extrusion: {code}")
            if "F" in words:
                maxf = max(maxf, words["F"] / 60)
            new = dict(pos)
            for ax in "XYZ":
                if ax in words:
                    new[ax] = words[ax]
            if all(a in new for a in "XYZ"):
                for ax, (lo, hi) in BOX.items():
                    if not lo - 1e-3 <= new[ax] <= hi + 1e-3:
                        problems.append(f"{fn}:{ln} {ax}={new[ax]} outside box")
                if all(a in pos for a in "XYZ"):
                    segs.append([(pos["X"], pos["Z"]), (new["X"], new["Z"])])
                    speeds.append(words.get("F", 0) / 60)
                    ys.append(new["Y"])
            pos = new
    if maxf > limit + 1e-6:
        problems.append(f"{fn}: max requested speed {maxf:.0f} mm/s > {limit:.0f}")
    paths[os.path.basename(fn)] = (segs, speeds, ys, maxf)
    print(f"{os.path.basename(fn):40s} moves={len(segs):5d}  max F={maxf:.0f} mm/s  "
          f"Y range={min(ys):.0f}-{max(ys):.0f}")

print("\nPROBLEMS:" if problems else "\nAll checks passed: inside safe box, no heat, no extrusion, "
      f"<={limit:.0f} mm/s.")
for p in problems:
    print("  ", p)

# Preview sheet (front view: X horizontal, Z vertical, as the audience sees it)
names = [n for n in paths if "showreel" not in n]
fig, axs = plt.subplots(2, 3, figsize=(15, 8.6), dpi=130)
for ax, name in zip(axs.flat, names):
    segs, speeds, _, _ = paths[name]
    lc = LineCollection(segs, cmap="viridis", linewidths=1.1)
    lc.set_array(speeds)
    lc.set_clim(0, limit)
    ax.add_collection(lc)
    ax.add_patch(plt.Rectangle((0, 0), 250, 183, fill=False, ls="--", lw=0.8, color="0.6"))
    ax.axhspan(0, 25, color="0.92")
    ax.text(125, 10, "keep-out: bed", ha="center", va="center", fontsize=7, color="0.45")
    ax.set_xlim(-5, 255); ax.set_ylim(-5, 188); ax.set_aspect("equal")
    t = name.replace("prusawire_", "").replace(".gcode", "")
    if "skywriter" in t:
        t += " (letters traced one at a time, overlaid here)"
    if "helix" in t:
        t += " (bed moves in Y too)"
    ax.set_title(t, fontsize=10)
    ax.set_xlabel("X (mm)", fontsize=8); ax.set_ylabel("Z (mm)", fontsize=8)
    ax.tick_params(labelsize=7)
cb = fig.colorbar(lc, ax=axs, shrink=0.6, pad=0.02)
cb.set_label("requested speed (mm/s)")
fig.suptitle("Prusawire CoreXZ demos: front view (X/Z plane), dashed = full travel", fontsize=12)
fig.savefig("preview.png", bbox_inches="tight")
print("wrote preview.png")
sys.exit(1 if problems else 0)
