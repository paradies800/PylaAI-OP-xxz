import os

import requests
from utils import load_toml_as_dict, save_dict_as_toml, api_base_url
class TrophyObserver:

    def __init__(self, brawler_list):
        self.history_file = "./cfg/match_history.toml"
        self.current_trophies = None
        self.current_wins = None
        self.match_history = self.load_history(brawler_list)
        self.match_history['total'] = {"defeat": 0, "victory": 0, "draw": 0}
        self.sent_match_history = {brawler: {"defeat": self.match_history[brawler]["defeat"],
                                             "victory": self.match_history[brawler]["victory"],
                                             "draw": 0}
                                   for brawler in brawler_list}
        self.win_streak = 0
        self.match_counter = 0  # New counter for the number of matches
        self.trophy_lose_ranges = [(49, 0), (299, 1), (599, 2), (799, 3), (999, 4), (1099, 5), (1199, 6), (1299, 7),
                                   (1499, 8), (1799, 9), (3999, 10), (float("inf"), 15)]
        self.trophy_win_ranges = [(1999, 10), (2499, 8), (2799, 6), (2999, 4), (3099, 2), (float("inf"), 1)]

        # Showdown trio: per-place trophy delta by trophy-range upper bound.
        # Columns: 1st, 2nd, 3rd, 4th
        # Source: official showdown trio trophy table.
        # Last row is a fallback for trophies above the documented range.
        self.showdown_trio_ranges = [
            (49,    (12, 5, 5, 5)),
            (99,    (11, 5, 4, -1)),
            (199,   (11, 5, 3, -1)),
            (299,   (11, 5, 2, -1)),
            (499,   (11, 5, 2, -2)),
            (599,   (11, 5, 1, -2)),
            (799,   (11, 5, 1, -3)),
            (999,   (11, 5, 1, -4)),
            (1099,  (11, 5, 0, -6)),
            (1199,  (11, 5, 0, -7)),
            (1299,  (11, 5, 0, -8)),
            (1499,  (11, 5, 0, -9)),
            (1799,  (11, 5, -5, -10)),
            (1999,  (11, 5, -5, -11)),
            (2199,  (9,  4, -5, -11)),
            (float("inf"), (9, 4, -5, -11)),
        ]
        self.crop_region = load_toml_as_dict("./cfg/lobby_config.toml")['lobby']['trophy_observer']
        self.trophies_multiplier = int(load_toml_as_dict("./cfg/general_config.toml")["trophies_multiplier"])

    def win_streak_gain(self):
        return min(self.win_streak - 1, 10) if self.current_trophies < 2000 else 0

    def apply_trophy_floor(self, old_trophies):
        """Once a brawler has reached 1000 trophies, they can't drop below it."""
        if old_trophies >= 1000 and self.current_trophies < 1000:
            self.current_trophies = 1000

    def calc_lost_decrement(self):
        for max_trophies, loss in self.trophy_lose_ranges:
            if float(self.current_trophies) <= float(max_trophies):
                return loss

    def calc_win_increment(self):
        for max_trophies, gain in self.trophy_win_ranges:
            if float(self.current_trophies) <= float(max_trophies):
                return gain*self.trophies_multiplier + self.win_streak_gain()

    def calc_showdown_delta(self, place_index):
        """Return trophy delta for showdown trio based on finishing place.

        place_index is 0-based: 0 = 1st, 1 = 2nd, 2 = 3rd, 3 = 4th.
        """
        for max_trophies, deltas in self.showdown_trio_ranges:
            if float(self.current_trophies) <= float(max_trophies):
                return deltas[place_index] * self.trophies_multiplier
        return 0

    def load_history(self, brawler_list):
        if os.path.exists(self.history_file):
            loaded_data = load_toml_as_dict(self.history_file)
        else:
            loaded_data = {}

        # Ensure each brawler has an entry
        for brawler in brawler_list:
            if brawler not in loaded_data:
                loaded_data[brawler] = {"defeat": 0, "victory": 0, "draw": 0}

        if "total" not in loaded_data:
            loaded_data["total"] = {"defeat": 0, "victory": 0, "draw": 0}

        return loaded_data

    def save_history(self):
        save_dict_as_toml(self.match_history, self.history_file)

    # Map showdown places to match_history victory/defeat buckets so the
    # existing history/API reporting keeps working unchanged.
    _showdown_place_index = {"1st": 0, "2nd": 1, "3rd": 2, "4th": 3}
    _showdown_place_to_bucket = {"1st": "victory", "2nd": "victory", "3rd": "defeat", "4th": "defeat"}

    def add_trophies(self, game_result, current_brawler):
        if current_brawler not in self.sent_match_history:
            self.sent_match_history[current_brawler] = {"defeat": 0, "victory": 0, "draw": 0}
        if current_brawler not in self.match_history:
            self.match_history[current_brawler] = {"defeat": 0, "victory": 0, "draw": 0}

        print(f"Found game result!: {game_result} win streak: {self.win_streak}")
        old = self.current_trophies
        bucket = None

        if game_result in self._showdown_place_index:
            # Showdown trio: place-based trophy delta.
            # Win streak rules (Brawl Stars showdown):
            #   1st, 2nd → streak grows, streak bonus applied
            #   3rd     → streak unchanged, no streak bonus
            #   4th     → streak reset, no streak bonus
            place_index = self._showdown_place_index[game_result]
            delta = self.calc_showdown_delta(place_index)

            # Update streak first so win_streak_gain() reflects this match.
            # 1st/2nd grow it, 4th resets, 3rd leaves it unchanged.
            if game_result in ("1st", "2nd"):
                self.win_streak += 1
            elif game_result == "4th":
                self.win_streak = 0

            streak_bonus = self.win_streak_gain() if game_result in ("1st", "2nd") else 0
            delta_with_bonus = delta + streak_bonus

            self.current_trophies += delta_with_bonus
            bucket = self._showdown_place_to_bucket[game_result]
            if streak_bonus:
                print(f"Showdown place: {game_result} → delta {delta:+d} (+{streak_bonus} streak bonus)")
            else:
                print(f"Showdown place: {game_result} → delta {delta:+d}")
        elif game_result == "victory":
            self.win_streak += 1
            self.current_trophies += self.calc_win_increment()
            bucket = "victory"
        elif game_result == "defeat":
            self.win_streak = 0
            self.current_trophies -= self.calc_lost_decrement()
            bucket = "defeat"
        elif game_result == "draw":
            print("Nothing changed. Draw detected")
            bucket = "draw"
        else:
            print("Catastrophic failure")
            return False

        self.apply_trophy_floor(old)
        print(f"Trophies : {old} -> {self.current_trophies}")
        print("Current wins:", self.current_wins)
        self.match_history[current_brawler][bucket] += 1
        self.match_history["total"][bucket] += 1

        self.match_counter += 1  # Increment the match counter
        if self.match_counter % 4 == 0:  # If every 4th match
            self.send_results_to_api()  # Send results to the API

        self.save_history()
        return True

    def add_win(self, game_result):
        # Treat victory (non-showdown) and 1st/2nd places (showdown) as wins
        if game_result == "victory" or game_result in ("1st", "2nd"):
            self.current_wins += 1



    def change_trophies(self, new):
        print(f"Trophies changed from {self.current_trophies} to {new}")
        self.current_trophies = new

    def send_results_to_api(self):
        # Prepare the data by calculating the difference between current and sent stats
        data = {}
        for brawler, stats in self.match_history.items():
            if brawler != "total":
                if brawler not in self.sent_match_history:
                    self.sent_match_history[brawler] = {"defeat": 0, "victory": 0, "draw": 0}
                new_stats = {
                    "wins": stats["victory"] - self.sent_match_history[brawler]["victory"],
                    "defeats": stats["defeat"] - self.sent_match_history[brawler]["defeat"],
                    "draws": 0
                }
                if any(new_stats.values()):  # Only include if there are new results
                    data[brawler] = new_stats

        if not data:  # No new data to send
            return

        if api_base_url != "localhost":
            # Send the POST request
            try:
                response = requests.post(f'https://{api_base_url}/api/brawlers', json=data)
                if response.status_code == 200:
                    print("Results successfully sent to API")
                    # Update sent_match_history with the latest totals
                    for brawler, stats in self.match_history.items():
                        if brawler != "total":
                            self.sent_match_history[brawler]["victory"] = stats["victory"]
                            self.sent_match_history[brawler]["defeat"] = stats["defeat"]
                            self.sent_match_history[brawler]["draw"] = 0
                else:
                    print(f"Failed to send results to API. Status code: {response.status_code}")
            except requests.exceptions.RequestException as e:
                print(f"Error sending results to API: {e}")
