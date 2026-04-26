import unittest
from unittest.mock import patch

from lobby_automation import LobbyAutomation


class DummyWindowController:
    width_ratio = 1.0
    height_ratio = 1.0

    def __init__(self):
        self.clicks = []

    def click(self, x, y):
        self.clicks.append((x, y))


class LowestTrophySlotTests(unittest.TestCase):
    @patch("lobby_automation.time.sleep", return_value=None)
    @patch("lobby_automation.load_toml_as_dict", return_value={"lowest_trophy_brawler_slot": 2})
    def test_slot_two_clicks_second_top_brawler_card(self, *_):
        automation = object.__new__(LobbyAutomation)
        automation.window_controller = DummyWindowController()

        automation.select_lowest_trophy_brawler()

        self.assertEqual(automation.window_controller.clicks[3], (787, 359))

    @patch("lobby_automation.time.sleep", return_value=None)
    @patch("lobby_automation.load_toml_as_dict", return_value={"lowest_trophy_brawler_slot": "bad"})
    def test_invalid_slot_falls_back_to_first_brawler_card(self, *_):
        automation = object.__new__(LobbyAutomation)
        automation.window_controller = DummyWindowController()

        automation.select_lowest_trophy_brawler()

        self.assertEqual(automation.window_controller.clicks[3], (422, 359))


if __name__ == "__main__":
    unittest.main()
