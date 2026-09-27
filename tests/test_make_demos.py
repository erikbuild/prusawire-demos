# ABOUTME: Unit and integration tests for the Prusawire demo generator.
# ABOUTME: Covers reachable-speed math, the Z zigzag demo, and the time estimator.
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import make_demos as md


def args_for(*argv):
    return md.parse_args(list(argv))


def zigzag(*argv):
    args = args_for(*argv)
    g = md.build(md.demo_zigzag, "Z zigzag", args)
    return g, args


def messages(g):
    return [ln[len("M117 "):] for ln in g.lines if ln.startswith("M117 ")]


class PeakSpeedTest(unittest.TestCase):
    def test_limited_by_stroke_height(self):
        args = args_for()
        self.assertAlmostEqual(md.peak_speed(16, 300, args), math.sqrt(2000 * 16))

    def test_limited_by_requested_speed(self):
        args = args_for()
        self.assertEqual(md.peak_speed(140, 200, args), 200)

    def test_limited_by_max_speed(self):
        args = args_for("--max-speed", "250")
        self.assertEqual(md.peak_speed(140, 300, args), 250)

    def test_uses_accel_flag(self):
        args = args_for("--max-speed", "1000", "--accel", "4000")
        self.assertAlmostEqual(md.peak_speed(100, 1000, args), math.sqrt(4000 * 100))


class ReversalHeightTest(unittest.TestCase):
    def test_stock_limits(self):
        self.assertAlmostEqual(md.reversal_height(300, args_for()), 45.0)

    def test_raised_accel(self):
        args = args_for("--max-speed", "400", "--accel", "4000")
        self.assertAlmostEqual(md.reversal_height(400, args), 40.0)


class ZigzagTest(unittest.TestCase):
    def test_teeth_use_full_safe_height(self):
        g, args = zigzag()
        zs = [mv[5] for mv in g.moves if mv[0] != "dwell"]
        self.assertAlmostEqual(min(zs), args.cz - 70)
        self.assertAlmostEqual(max(zs), args.cz + 70)

    def test_stock_labels_show_reached_speeds(self):
        g, _ = zigzag()
        msgs = messages(g)
        for spd in (100, 200, 300):
            self.assertIn(f"Z zigzag {spd} mm/s", msgs)
        self.assertIn("Top-speed reversals 300 mm/s", msgs)
        self.assertEqual(g.warnings, [])

    def test_buzz_strokes_just_reach_top_speed(self):
        g, args = zigzag()
        start = next(i for i, (_, t) in enumerate(g.markers)
                     if t.startswith("Top-speed reversals"))
        idx = g.markers[start][0]
        zs = [mv[5] for mv in g.moves[idx:] if mv[0] != "dwell"]
        # strokes alternate cz +/- 22.5 (45 mm = 300^2 / 2000)
        self.assertAlmostEqual(max(zs), args.cz + 22.5)
        self.assertAlmostEqual(min(zs), args.cz - 22.5)

    def test_raised_limits_add_faster_tiers(self):
        g, _ = zigzag("--max-speed", "450", "--accel", "4000",
                      "--speeds", "100", "200", "300", "400", "450")
        msgs = messages(g)
        self.assertIn("Z zigzag 400 mm/s", msgs)
        self.assertIn("Z zigzag 450 mm/s", msgs)
        self.assertIn("Top-speed reversals 450 mm/s", msgs)
        self.assertEqual(g.warnings, [])

    def test_unreachable_tier_is_labelled_honestly_and_warned(self):
        # sqrt(2000 * 140) = 529 mm/s is the most a 140 mm tooth can reach
        g, _ = zigzag("--max-speed", "600", "--speeds", "300", "600")
        msgs = messages(g)
        self.assertIn("Z zigzag 529 mm/s", msgs)
        self.assertNotIn("Z zigzag 600 mm/s", msgs)
        self.assertTrue(any("600" in w and "529" in w for w in g.warnings))

    def test_all_moves_inside_safe_box(self):
        g, _ = zigzag("--max-speed", "600", "--accel", "1000")
        for mv in g.moves:
            if mv[0] == "dwell":
                continue
            md.GcodeWriter.check(g, mv[3], mv[4], mv[5])


class DemoListTest(unittest.TestCase):
    def test_no_skywriter(self):
        slugs = [slug for slug, _, _ in md.DEMOS]
        self.assertEqual(slugs, ["01_z_zigzag", "02_z_sprint", "03_one_motor_diamond",
                                 "04_vertical_curves", "05_helix_3d"])

    def test_skywriter_and_led_options_are_gone(self):
        for opt in (["--text", "HI"], ["--sky-mode", "word"], ["--draw-speed", "50"],
                    ["--led", "toolhead"]):
            with self.assertRaises(SystemExit), open(os.devnull, "w") as null:
                stderr, sys.stderr = sys.stderr, null
                try:
                    args_for(*opt)
                finally:
                    sys.stderr = stderr

    def test_no_led_commands_emitted(self):
        g = md.build_showreel(args_for())
        self.assertFalse(any(ln.startswith("SET_LED") for ln in g.lines))


class EstimateTest(unittest.TestCase):
    def test_faster_limits_give_shorter_estimate(self):
        stock = args_for()
        fast = args_for("--max-speed", "450", "--accel", "4000")
        t_stock = md.estimate_seconds(md.build(md.demo_zigzag, "z", stock).moves, stock)
        t_fast = md.estimate_seconds(md.build(md.demo_zigzag, "z", stock).moves, fast)
        self.assertLess(t_fast, t_stock)

    def test_single_move_time(self):
        # 100 mm at 100 mm/s, 2000 mm/s^2: two 0.05 s ramps (2.5 mm each) + 95 mm cruise
        args = args_for()
        t = md.estimate_seconds([(0, 0, 0, 100, 0, 0, 100)], args)
        self.assertAlmostEqual(t, 0.05 + 0.05 + 0.95)


if __name__ == "__main__":
    unittest.main()
