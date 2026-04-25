import unittest

from window_controller import (
    WindowController,
    _infer_ldplayer_index,
    _infer_mumu_index,
)


class EmulatorProfileMappingTest(unittest.TestCase):
    def test_mumu_ports_map_to_matching_profile_index(self):
        self.assertEqual(_infer_mumu_index(16384), 0)
        self.assertEqual(_infer_mumu_index(16416), 1)
        self.assertEqual(_infer_mumu_index(16448), 2)

    def test_ldplayer_ports_map_to_matching_profile_index(self):
        self.assertEqual(_infer_ldplayer_index(5555), 0)
        self.assertEqual(_infer_ldplayer_index(5557), 1)
        self.assertEqual(_infer_ldplayer_index(5559), 2)

    def test_restart_target_follows_actual_connected_mumu_device(self):
        controller = object.__new__(WindowController)
        controller.selected_emulator = "MuMu"
        controller.connected_serial = "127.0.0.1:16448"
        controller.configured_port = 16384
        controller.configured_serial = "127.0.0.1:16384"
        controller.emulator_profile_index = 0
        controller.emulator_profile_index_is_auto = True

        controller.sync_restart_target_to_connected_device()

        self.assertEqual(controller.configured_port, 16448)
        self.assertEqual(controller.configured_serial, "127.0.0.1:16448")
        self.assertEqual(controller.emulator_profile_index, 2)


if __name__ == "__main__":
    unittest.main()
