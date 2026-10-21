# ABOUTME: Unit and integration tests for the homing measurement tools in tools/.
# ABOUTME: Covers GET_POSITION parsing, CoreXZ count math, and the low-current stage scripts.
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))
import homing_stage_slips as hss
import x_home_repeatability as xhr

# Moonraker gcode_store entries recorded on enceladus on 2026-10-18, oldest first.
OLDER_POSITION = {
    "message": "// mcu: stepper_x:-2861 stepper_y:-16 stepper_z:-5055\n"
               "// stepper: stepper_x:135.000000 stepper_y:105.000000 stepper_z:115.000000\n"
               "// kinematic: X:125.000000 Y:105.000000 Z:10.000000",
    "time": 1792371835.3101637, "type": "response"}
HOME_COMMAND = {"message": "G90\nG1 Z20 F1200\nG1 X125.0 Y105.0 F6000\nG28 X\nG90",
                "time": 1792371835.3413482, "type": "command"}
PROBE_RESULT = {"message": "// Result is z=1.610000", "time": 1792371848.0298831,
                "type": "response"}
POSITION_COMMAND = {"message": "M400\nGET_POSITION", "time": 1792371848.094039,
                    "type": "command"}
NEWER_POSITION = {
    "message": "// mcu: stepper_x:-2842 stepper_y:-16 stepper_z:-5036\n"
               "// stepper: stepper_x:135.000000 stepper_y:105.000000 stepper_z:115.000000\n"
               "// kinematic: X:125.000000 Y:105.000000 Z:10.000000",
    "time": 1792371848.901261, "type": "response"}

# Enceladus: 16T pulleys (rotation_distance 32), 16 microsteps, upstream homing macros.
ENCELADUS_SETTINGS = {
    "stepper_x": {"rotation_distance": 32.0, "microsteps": 16, "full_steps_per_rotation": 200},
    "tmc2130 stepper_x": {"run_current": 0.3480291},
    "tmc2130 stepper_z": {"run_current": 0.3480291},
    "gcode_macro _home_x": {"variable_home_current_divisor": "3"},
}


class McuCountsFromStoreTest(unittest.TestCase):
    def test_reads_every_stepper(self):
        counts = xhr.mcu_counts_from_store([NEWER_POSITION])
        self.assertEqual(counts, {"stepper_x": -2842, "stepper_y": -16, "stepper_z": -5036})

    def test_newest_position_wins(self):
        store = [OLDER_POSITION, HOME_COMMAND, PROBE_RESULT, POSITION_COMMAND, NEWER_POSITION]
        self.assertEqual(xhr.mcu_counts_from_store(store)["stepper_x"], -2842)

    def test_skips_entries_after_the_position(self):
        store = [OLDER_POSITION, HOME_COMMAND, PROBE_RESULT]
        self.assertEqual(xhr.mcu_counts_from_store(store)["stepper_x"], -2861)

    def test_missing_position_raises(self):
        with self.assertRaises(RuntimeError):
            xhr.mcu_counts_from_store([HOME_COMMAND, PROBE_RESULT, POSITION_COMMAND])


class AxisShiftTest(unittest.TestCase):
    def test_both_motors_equal_is_pure_x(self):
        self.assertEqual(xhr.axis_shift(100, 100), (100, 0))

    def test_motors_opposite_is_pure_z(self):
        self.assertEqual(xhr.axis_shift(100, -100), (0, 100))

    def test_motor_b_slip_splits_into_x_and_z(self):
        # The 2026-10-18 slip: motor B lost 3 electrical cycles, motor A none.
        self.assertEqual(xhr.axis_shift(0, -192), (-96, 96))


class StepsFromSettingsTest(unittest.TestCase):
    def test_usteps_per_mm_for_16t_pulleys(self):
        self.assertEqual(xhr.usteps_per_mm(ENCELADUS_SETTINGS), 100)

    def test_usteps_per_mm_for_rotation_distance_40(self):
        settings = {"stepper_x": dict(ENCELADUS_SETTINGS["stepper_x"], rotation_distance=40.0)}
        self.assertEqual(xhr.usteps_per_mm(settings), 80)

    def test_electrical_cycle_is_four_full_steps(self):
        self.assertEqual(hss.usteps_per_cycle(ENCELADUS_SETTINGS), 64)

    def test_electrical_cycle_follows_microsteps(self):
        settings = {"stepper_x": dict(ENCELADUS_SETTINGS["stepper_x"], microsteps=32)}
        self.assertEqual(hss.usteps_per_cycle(settings), 128)


class MotorCyclesTest(unittest.TestCase):
    def test_motor_b_slip_is_three_cycles_on_b_only(self):
        self.assertEqual(hss.motor_cycles(-96, 96, 64), (0, -3))

    def test_pure_x_moves_both_motors_together(self):
        self.assertEqual(hss.motor_cycles(64, 0, 64), (1, 1))


class MarginStagesTest(unittest.TestCase):
    """The low-current scripts must match the ones that ran on enceladus on 2026-10-18."""

    def test_hold_drops_both_motors_to_homing_current_then_restores(self):
        stages = hss.margin_stages(ENCELADUS_SETTINGS)
        self.assertEqual(stages["hold"], (
            "SET_TMC_CURRENT STEPPER=stepper_x CURRENT=0.1160097\n"
            "SET_TMC_CURRENT STEPPER=stepper_z CURRENT=0.1160097\n"
            "G4 P10000\n"
            "SET_TMC_CURRENT STEPPER=stepper_x CURRENT=0.3480291\n"
            "SET_TMC_CURRENT STEPPER=stepper_z CURRENT=0.3480291"))

    def test_backoff_moves_away_at_homing_current(self):
        stages = hss.margin_stages(ENCELADUS_SETTINGS)
        self.assertEqual(stages["backoff"], (
            "SET_TMC_CURRENT STEPPER=stepper_x CURRENT=0.1160097\n"
            "SET_TMC_CURRENT STEPPER=stepper_z CURRENT=0.1160097\n"
            "G91\n"
            "G1 X5 F1200\n"
            "G4 P250\n"
            "SET_TMC_CURRENT STEPPER=stepper_x CURRENT=0.3480291\n"
            "SET_TMC_CURRENT STEPPER=stepper_z CURRENT=0.3480291"))

    def test_cold_path_stages_do_not_need_settings(self):
        stages = hss.STAGE_SETS["cold-path"]({})
        self.assertEqual(list(stages), ["z", "xy", "y", "full"])


if __name__ == "__main__":
    unittest.main()
