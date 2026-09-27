# ABOUTME: End-to-end tests for install-demo.sh, run against a temporary printer_data folder.
# ABOUTME: Feeds YES/no answers on stdin and checks the files the script leaves behind.
import glob
import os
import subprocess
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(ROOT, "install-demo.sh")
INCLUDE = "[include prusawire_demo.cfg]"
PRINTER_CFG = "[printer]\nkinematics: corexz\n\n#*# <---------------------- SAVE_CONFIG ---------------------->\n#*# [bltouch]\n#*# z_offset = 1.0\n"


class InstallScriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data = self.tmp.name
        os.makedirs(os.path.join(self.data, "gcodes"))
        os.makedirs(os.path.join(self.data, "config"))
        self.write_printer_cfg(PRINTER_CFG)

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, *parts):
        return os.path.join(self.data, *parts)

    def write_printer_cfg(self, text):
        with open(self.path("config", "printer.cfg"), "w") as f:
            f.write(text)

    def printer_cfg(self):
        with open(self.path("config", "printer.cfg")) as f:
            return f.read()

    def run_script(self, answers):
        env = dict(os.environ, PRINTER_DATA=self.data)
        return subprocess.run(["bash", SCRIPT], input=answers, env=env,
                              capture_output=True, text=True, cwd=self.data)

    def test_all_default_answers_install_everything(self):
        r = self.run_script("\n\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stderr, "")
        repo = sorted(os.path.basename(p) for p in glob.glob(os.path.join(ROOT, "gcode", "*.gcode")))
        copied = sorted(os.listdir(self.path("gcodes")))
        self.assertEqual(copied, repo)
        self.assertIn(f"Copied {len(repo)} demo files", r.stdout)
        self.assertTrue(os.path.exists(self.path("config", "prusawire_demo.cfg")))
        self.assertTrue(self.printer_cfg().startswith(INCLUDE + "\n"))
        self.assertTrue(self.printer_cfg().endswith(PRINTER_CFG))
        self.assertEqual(len(glob.glob(self.path("config", "printer.cfg.bak-*"))), 1)
        self.assertIn("Restart Klipper", r.stdout)

    def test_yes_answers_are_case_insensitive(self):
        r = self.run_script("Y\nyes\nYES\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.printer_cfg().startswith(INCLUDE))

    def test_all_no_changes_nothing(self):
        r = self.run_script("n\nno\nN\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(os.listdir(self.path("gcodes")), [])
        self.assertEqual(sorted(os.listdir(self.path("config"))), ["printer.cfg"])
        self.assertEqual(self.printer_cfg(), PRINTER_CFG)
        self.assertNotIn("Restart Klipper", r.stdout)

    def test_gcode_only_needs_no_restart(self):
        r = self.run_script("y\nn\nn\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotEqual(os.listdir(self.path("gcodes")), [])
        self.assertNotIn("Restart Klipper", r.stdout)

    def test_end_of_input_takes_defaults(self):
        r = self.run_script("")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(self.printer_cfg().startswith(INCLUDE))

    def test_rerun_does_not_duplicate_include(self):
        self.run_script("\n\n\n")
        r = self.run_script("\n\n\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.printer_cfg().count(INCLUDE), 1)
        self.assertIn("already includes", r.stdout)
        self.assertEqual(len(glob.glob(self.path("config", "printer.cfg.bak-*"))), 1)

    def test_existing_include_with_spacing_is_detected(self):
        self.write_printer_cfg("[include  prusawire_demo.cfg ]\n" + PRINTER_CFG)
        r = self.run_script("\n\n\n")
        self.assertIn("already includes", r.stdout)
        self.assertEqual(self.printer_cfg().count("prusawire_demo.cfg"), 1)

    def test_include_skipped_when_cfg_not_installed(self):
        r = self.run_script("n\nn\ny\n")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.printer_cfg(), PRINTER_CFG)
        self.assertIn("prusawire_demo.cfg is not in", r.stdout)

    def test_missing_printer_cfg_is_an_error(self):
        os.remove(self.path("config", "printer.cfg"))
        r = self.run_script("\n\n\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("printer.cfg not found", r.stdout)

    def test_missing_gcodes_folder_is_an_error(self):
        os.rmdir(self.path("gcodes"))
        r = self.run_script("\n\n\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("gcodes folder not found", r.stdout)
        self.assertTrue(self.printer_cfg().startswith(INCLUDE))


if __name__ == "__main__":
    unittest.main()
