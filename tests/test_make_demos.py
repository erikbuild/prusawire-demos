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


def motor_speed(mv):
    x0, y0, z0, x1, y1, z1, v = mv
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    return v * (abs(dx) + abs(dz)) / math.sqrt(dx * dx + dy * dy + dz * dz)


class AllowedSpeedTest(unittest.TestCase):
    def test_pure_axis_moves_are_not_capped(self):
        args = args_for()
        self.assertEqual(md.allowed_speed(300, 100, 0, 100, args), 300)
        self.assertEqual(md.allowed_speed(300, 0, 100, 100, args), 300)

    def test_diagonal_is_capped_by_motor_speed(self):
        args = args_for()
        d = math.hypot(100, 100)
        self.assertAlmostEqual(md.allowed_speed(300, 100, 100, d, args), 300 / math.sqrt(2))
        self.assertAlmostEqual(md.allowed_speed(300, -100, 100, d, args), 300 / math.sqrt(2))

    def test_shallow_angle(self):
        args = args_for("--max-motor-speed", "350")
        d = math.hypot(30, 40)
        self.assertAlmostEqual(md.allowed_speed(300, 30, 40, d, args), 350 * 50 / 70)

    def test_slow_request_is_unchanged(self):
        args = args_for()
        self.assertEqual(md.allowed_speed(150, 100, 100, math.hypot(100, 100), args), 150)

    def test_max_speed_still_applies(self):
        args = args_for("--max-speed", "250", "--max-motor-speed", "1000")
        self.assertEqual(md.allowed_speed(300, 0, 100, 100, args), 250)

    def test_y_travel_counts_toward_distance_only(self):
        args = args_for()
        d = math.sqrt(100 ** 2 + 100 ** 2 + 100 ** 2)
        self.assertAlmostEqual(md.allowed_speed(300, 100, 100, d, args), 300 * d / 200)


class MotorSpeedLimitTest(unittest.TestCase):
    def assert_motors_within(self, g, limit):
        worst = max(motor_speed(mv) for mv in g.moves if mv[0] != "dwell")
        self.assertLessEqual(worst, limit + 1e-6)

    def test_every_demo_respects_default_motor_limit(self):
        args = args_for()
        for slug, title, fn in md.DEMOS:
            with self.subTest(slug):
                self.assert_motors_within(md.build(fn, title, args), 300)

    def test_showreel_respects_raised_motor_limit(self):
        args = args_for("--max-speed", "450", "--accel", "4000", "--max-motor-speed", "400")
        self.assert_motors_within(md.build_showreel(args), 400)

    def test_emitted_feedrate_matches_capped_speed(self):
        args = args_for()
        g = md.build(md.demo_one_motor, "diamond", args)
        diagonals = [mv for mv in g.moves if mv[0] != "dwell"
                     and abs(abs(mv[3] - mv[0]) - abs(mv[5] - mv[2])) < 1e-6 and mv[3] != mv[0]]
        self.assertGreater(len(diagonals), 10)
        for mv in diagonals:
            self.assertAlmostEqual(mv[6], 300 / math.sqrt(2))
        f = 300 / math.sqrt(2) * 60
        self.assertTrue(any(ln.endswith(f" F{f:.0f}") for ln in g.lines))


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
        # 300 mm/s teeth lean 13 mm per 140 mm, so the motor cap allows 275 mm/s
        for spd in (100, 200, 275):
            self.assertIn(f"Z zigzag {spd} mm/s", msgs)
        self.assertEqual(g.warnings, [])
        self.assertEqual(g.warnings, [])

    def buzz(self, *argv):
        g, args = zigzag(*argv)
        idx, label = next((i, t) for i, t in g.markers if t.startswith("Top-speed reversals"))
        label_speed = float(label.split()[2])
        strokes = [mv for mv in g.moves[idx + 1:] if mv[0] != "dwell"][1:-1]
        return args, label_speed, strokes

    def test_buzz_strokes_just_reach_labelled_speed(self):
        args, label_speed, strokes = self.buzz()
        heights = {round(abs(mv[5] - mv[2]), 6) for mv in strokes}
        self.assertEqual(len(heights), 1)
        height = heights.pop()
        # tall enough to reach the label, and no taller than needed
        self.assertGreaterEqual(math.sqrt(args.accel * height), label_speed - 0.5)
        self.assertLess(height, md.reversal_height(label_speed + 5, args))
        for mv in strokes:
            self.assertGreaterEqual(mv[6], label_speed - 0.5)

    def test_buzz_label_at_stock_limits(self):
        _, label_speed, _ = self.buzz()
        self.assertLess(label_speed, 300)
        self.assertGreater(label_speed, 200)

    def test_raised_limits_add_faster_tiers(self):
        g, _ = zigzag("--max-speed", "450", "--accel", "4000", "--max-motor-speed", "600",
                      "--speeds", "100", "200", "300", "400", "450")
        msgs = messages(g)
        self.assertIn("Z zigzag 400 mm/s", msgs)
        self.assertIn("Z zigzag 450 mm/s", msgs)
        self.assertIn("Top-speed reversals 450 mm/s", msgs)
        self.assertEqual(g.warnings, [])

    def test_unreachable_tier_is_labelled_honestly_and_warned(self):
        # sqrt(2000 * 140) = 529 mm/s is the most a 140 mm tooth can reach
        g, _ = zigzag("--max-speed", "600", "--max-motor-speed", "900", "--speeds", "300", "600")
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
