import unittest
from unittest.mock import patch

from window_controller import WindowController, _foreground_package_from_text


class LongRunWatchdogTests(unittest.TestCase):
    def test_foreground_package_parser_handles_current_focus(self):
        text = "mCurrentFocus=Window{123 u0 com.supercell.brawlstars/com.supercell.titan.GameApp}"
        self.assertEqual(_foreground_package_from_text(text), "com.supercell.brawlstars")

    def test_foreground_package_parser_handles_focused_app(self):
        text = "mFocusedApp=ActivityRecord{123 u0 com.android.launcher/.Launcher t1}"
        self.assertEqual(_foreground_package_from_text(text), "com.android.launcher")

    @patch("window_controller.time.time")
    def test_emulator_restart_respects_cooldown(self, mock_time):
        controller = object.__new__(WindowController)
        controller.last_emulator_restart_time = 100.0
        controller.emulator_restart_cooldown = 180.0
        mock_time.return_value = 150.0

        self.assertFalse(controller.restart_emulator_profile())


if __name__ == "__main__":
    unittest.main()
