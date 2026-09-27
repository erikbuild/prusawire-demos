# ABOUTME: End-to-end tests: run the generator CLI, then the independent checker on its output.
# ABOUTME: Uses the real scripts in subprocesses with temporary output folders.
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def run(*cmd, cwd):
    return subprocess.run([sys.executable, *cmd], cwd=cwd, capture_output=True, text=True)


class EndToEndTest(unittest.TestCase):
    def generate_and_check(self, gen_args, check_args):
        with tempfile.TemporaryDirectory() as tmp:
            gen = run(os.path.join(ROOT, "make_demos.py"), "--out", tmp, *gen_args, cwd=tmp)
            self.assertEqual(gen.returncode, 0, gen.stderr)
            self.assertEqual(gen.stderr, "")
            chk = run(os.path.join(ROOT, "check_and_preview.py"), tmp, *check_args, cwd=tmp)
            self.assertTrue(os.path.exists(os.path.join(tmp, "preview.png")))
            return gen, chk

    def test_stock_build_passes_stock_check(self):
        gen, chk = self.generate_and_check([], [])
        self.assertNotIn("WARNING", gen.stdout)
        self.assertEqual(chk.returncode, 0, chk.stdout)
        self.assertIn("All checks passed", chk.stdout)
        self.assertIn("<=300 mm/s", chk.stdout)

    def test_raised_build_passes_matching_check(self):
        fast = ["--max-speed", "450", "--accel", "4000",
                "--speeds", "100", "200", "300", "400", "450"]
        gen, chk = self.generate_and_check(fast, ["--max-speed", "450"])
        self.assertNotIn("WARNING", gen.stdout)
        self.assertIn("450 mm/s, 4000 mm/s^2", gen.stdout)
        self.assertEqual(chk.returncode, 0, chk.stdout)
        self.assertIn("<=450 mm/s", chk.stdout)

    def test_raised_build_fails_stock_check(self):
        _, chk = self.generate_and_check(["--max-speed", "450", "--speeds", "300", "450"], [])
        self.assertEqual(chk.returncode, 1)
        self.assertIn("max requested speed 450 mm/s > 300", chk.stdout)

    def test_unreachable_tier_warns(self):
        gen, _ = self.generate_and_check(["--max-speed", "600", "--speeds", "300", "600"],
                                         ["--max-speed", "600"])
        self.assertIn("WARNING: Z zigzag tier 600 mm/s only reaches 529 mm/s", gen.stdout)


if __name__ == "__main__":
    unittest.main()
