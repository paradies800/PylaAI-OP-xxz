import asyncio
import platform
import sys
import time

import cv2

from logger_setup import setup_logging_if_enabled

setup_logging_if_enabled()

import window_controller
from gui.hub import Hub
from gui.login import login
from gui.main import App
from gui.select_brawler import SelectBrawler
from lobby_automation import LobbyAutomation
from play import Play
from runtime_control import RuntimeControlWindow
from stage_manager import StageManager
from state_finder import get_state
from time_management import TimeManagement
from utils import (
    api_base_url,
    async_notify_user,
    check_version,
    cprint,
    current_wall_model_is_latest,
    extract_text_strings,
    get_brawler_list,
    get_latest_version,
    get_latest_wall_model_file,
    load_toml_as_dict,
    update_missing_brawlers_info,
    update_wall_model_classes,
)
from window_controller import WindowController

if platform.architecture()[0] != "64bit":
    print("\nWARNING: PylaAI is running on 32-bit Python.")
    print("If IPS is very low, run python tools/performance_check.py to verify ONNX and emulator frame speed.")
    print(f"Current Python: {sys.executable}")

pyla_version = load_toml_as_dict("./cfg/general_config.toml")['pyla_version']

def pyla_main(data):
    class Main:

        def __init__(self):
            self.window_controller = WindowController()
            self.Play = Play(*self.load_models(), self.window_controller)
            self.Time_management = TimeManagement()
            self.lobby_automator = LobbyAutomation(self.window_controller)
            self.Stage_manager = StageManager(data, self.lobby_automator, self.window_controller)
            self.states_requiring_data = ["lobby"]
            if data[0]['automatically_pick']:
                print("Picking brawler automatically")
                self.lobby_automator.select_brawler(data[0]['brawler'])
            self.Play.current_brawler = data[0]['brawler']
            self.no_detections_action_threshold = 60 * 8
            self.initialize_stage_manager()
            self.state = None
            try:
                general_config = load_toml_as_dict("cfg/general_config.toml")
                self.max_ips = int(general_config['max_ips'])
            except ValueError:
                self.max_ips = None
                general_config = load_toml_as_dict("cfg/general_config.toml")
            print(
                "Performance config:",
                f"max_ips={self.max_ips or 'auto'}",
                f"scrcpy_max_fps={general_config.get('scrcpy_max_fps', 'default')}",
                f"onnx_cpu_threads={general_config.get('onnx_cpu_threads', 'auto')}",
            )
            self.visual_debug = load_toml_as_dict("cfg/general_config.toml").get('visual_debug', 'no') == "yes"
            self.run_for_minutes = int(load_toml_as_dict("cfg/general_config.toml")['run_for_minutes'])
            self.start_time = time.time()
            self.time_to_stop = False
            self.in_cooldown = False
            self.cooldown_start_time = 0
            self.cooldown_duration = 3 * 60
            self.match_ready_at = 0.0
            self.match_warmup_seconds = float(load_toml_as_dict("cfg/bot_config.toml").get("match_warmup_seconds", 4.0))
            time_thresholds = load_toml_as_dict("cfg/time_tresholds.toml")
            self.visual_freeze_check_interval = float(time_thresholds.get("visual_freeze_check_interval", 1.0))
            self.visual_freeze_restart_seconds = float(time_thresholds.get("visual_freeze_restart", 45.0))
            self.visual_freeze_diff_threshold = float(time_thresholds.get("visual_freeze_diff_threshold", 0.35))
            self.last_visual_freeze_check = 0.0
            self.last_visual_change_time = time.time()
            self.last_visual_sample = None
            self.lobby_start_retry_interval = float(time_thresholds.get("lobby_start_retry", 8.0))
            self.lobby_stuck_restart_seconds = float(time_thresholds.get("lobby_stuck_restart", 120.0))
            self.lobby_entered_at = None
            self.last_lobby_start_press = 0.0
            self.last_stale_feed_recovery = 0.0
            self.stale_feed_recovery_attempts = 0
            self.last_stale_feed_message = 0.0
            self.last_disconnect_check = 0.0
            self.disconnect_reload_attempts = 0
            self.last_processed_frame_id = -1
            self.ips_ema = None
            self.low_frame_fps_warning_time = 0.0
            self.disconnect_ocr_interval = 6.0
            self.control_window = RuntimeControlWindow()
            self.control_window.start()
            self.was_paused = False
            self.pause_started_at = None

        def initialize_stage_manager(self):
            self.Stage_manager.Trophy_observer.win_streak = data[0]['win_streak']
            self.Stage_manager.Trophy_observer.current_trophies = data[0]['trophies']
            self.Stage_manager.Trophy_observer.current_wins = data[0]['wins'] if data[0]['wins'] != "" else 0

        @staticmethod
        def load_models():
            folder_path = "./models/"
            model_names = ['mainInGameModel.onnx', 'tileDetector.onnx']
            loaded_models = []

            for name in model_names:
                loaded_models.append(folder_path + name)
            return loaded_models

        def restart_brawl_stars(self):
            self.window_controller.restart_brawl_stars()
            self.window_controller.restart_scrcpy_client()
            self.reset_visual_freeze_watchdog()
            self.lobby_entered_at = None
            self.last_lobby_start_press = 0.0
            self.last_processed_frame_id = -1
            self.Play.time_since_detections["player"] = time.time()
            self.Play.time_since_detections["enemy"] = time.time()
            if self.window_controller.device.app_current().package != window_controller.BRAWL_STARS_PACKAGE:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    screenshot = self.window_controller.screenshot()
                    loop.run_until_complete(async_notify_user("bot_is_stuck", screenshot))
                finally:
                    loop.close()
                print("Bot got stuck. User notified. Shutting down.")
                self.window_controller.keys_up(list("wasd"))
                self.window_controller.close()
                import sys
                sys.exit(1)

        def reset_visual_freeze_watchdog(self):
            self.last_visual_sample = None
            self.last_visual_freeze_check = 0.0
            self.last_visual_change_time = time.time()

        def handle_visual_freeze(self, frame):
            if self.state != "match":
                self.reset_visual_freeze_watchdog()
                return False

            now = time.time()
            if now < self.match_ready_at or now - self.last_visual_freeze_check < self.visual_freeze_check_interval:
                return False
            self.last_visual_freeze_check = now

            sample = cv2.resize(frame, (96, 54), interpolation=cv2.INTER_AREA)
            sample = cv2.cvtColor(sample, cv2.COLOR_RGB2GRAY)
            if self.last_visual_sample is None:
                self.last_visual_sample = sample
                self.last_visual_change_time = now
                return False

            diff = float(cv2.absdiff(sample, self.last_visual_sample).mean())
            self.last_visual_sample = sample
            if diff >= self.visual_freeze_diff_threshold:
                self.last_visual_change_time = now
                return False

            frozen_for = now - self.last_visual_change_time
            if frozen_for < self.visual_freeze_restart_seconds:
                return False

            print(
                f"Match image did not change for {frozen_for:.1f}s "
                f"(diff {diff:.3f}); restarting Brawl Stars and scrcpy."
            )
            self.window_controller.keys_up(list("wasd"))
            self.restart_brawl_stars()
            return True

        def handle_lobby_watchdog(self, state):
            now = time.time()
            if state != "lobby" or self.in_cooldown:
                if state != "lobby":
                    self.lobby_entered_at = None
                return False

            if self.lobby_entered_at is None:
                self.lobby_entered_at = now

            if now - self.last_lobby_start_press >= self.lobby_start_retry_interval:
                print("Lobby watchdog: pressing start again.")
                self.window_controller.keys_up(list("wasd"))
                self.window_controller.press_key("Q")
                self.last_lobby_start_press = now

            lobby_age = now - self.lobby_entered_at
            if lobby_age < self.lobby_stuck_restart_seconds:
                return False

            print(f"Lobby did not enter a match for {lobby_age:.1f}s; restarting Brawl Stars.")
            self.restart_brawl_stars()
            return True

        def manage_time_tasks(self, frame):
            if self.handle_disconnect_screen(frame):
                return

            if self.Time_management.state_check():
                state = get_state(frame)
                previous_state = self.state
                self.state = state
                if state != "match":
                    self.Play.time_since_last_proceeding = time.time()
                if previous_state == "match" and state != "match":
                    self.Play.reset_match_control_state()
                elif previous_state != "match" and state == "match":
                    self.Play.reset_match_control_state()
                    self.match_ready_at = time.time() + self.match_warmup_seconds
                frame_data = None
                self.Stage_manager.do_state(state, frame_data)
                self.handle_lobby_watchdog(state)

            if self.Time_management.no_detections_check():
                frame_data = self.Play.time_since_detections
                for key, value in frame_data.items():
                    if time.time() - value > self.no_detections_action_threshold:
                        self.restart_brawl_stars()

            if self.Time_management.idle_check():
                #print("check for idle!")
                self.lobby_automator.check_for_idle(frame)

        def handle_disconnect_screen(self, frame):
            if time.time() - self.last_disconnect_check < self.disconnect_ocr_interval:
                return False
            self.last_disconnect_check = time.time()

            h, w = frame.shape[:2]
            dialog_crop = frame[int(h * 0.32):int(h * 0.62), int(w * 0.24):int(w * 0.76)]
            dialog_mean = float(dialog_crop.mean())
            dialog_std = float(dialog_crop.std())
            dialog_hsv = cv2.cvtColor(dialog_crop, cv2.COLOR_RGB2HSV)
            dialog_saturation = float(dialog_hsv[:, :, 1].mean())
            if dialog_mean > 90 or dialog_std > 75 or dialog_saturation > 85:
                return False

            center_crop = frame[int(h * 0.22):int(h * 0.55), int(w * 0.15):int(w * 0.70)]
            try:
                text = " ".join(extract_text_strings(center_crop))
            except Exception as e:
                print(f"Could not OCR disconnect screen: {e}")
                return False

            if (
                    "reload" not in text
                    and "disconnect" not in text
                    and "disconnected" not in text
                    and "idle" not in text
            ):
                return False

            self.disconnect_reload_attempts += 1
            self.window_controller.keys_up(list("wasd"))
            print(f"Disconnect/reload screen detected, recovery attempt {self.disconnect_reload_attempts}.")
            if self.disconnect_reload_attempts >= 3:
                print("Reload did not clear disconnect screen; restarting Brawl Stars.")
                self.restart_brawl_stars()
                self.disconnect_reload_attempts = 0
            else:
                self.window_controller.click(550, 450, already_include_ratio=False)
                time.sleep(3)
            return True

        def handle_stale_scrcpy_feed(self, frame_time=None):
            now = time.time()
            stale_age = now - frame_time if frame_time else 0
            age_text = f"{stale_age:.1f}s old" if frame_time else "missing"
            self.Play.window_controller.keys_up(list("wasd"))

            if now - self.last_stale_feed_recovery < 5:
                if now - self.last_stale_feed_message > 2:
                    remaining = 5 - (now - self.last_stale_feed_recovery)
                    print(f"Scrcpy frame is still {age_text}; retrying recovery in {remaining:.1f}s.")
                    self.last_stale_feed_message = now
                return

            self.last_stale_feed_recovery = now
            self.stale_feed_recovery_attempts += 1

            if self.stale_feed_recovery_attempts >= 3 or stale_age > 45:
                print("Scrcpy feed is still frozen; restarting Brawl Stars and scrcpy.")
                self.restart_brawl_stars()
                self.stale_feed_recovery_attempts = 0
            else:
                print(f"Scrcpy frame is {age_text}; restarting scrcpy feed.")
                self.window_controller.restart_scrcpy_client()

        def handle_pause_control(self):
            if not self.control_window.is_paused():
                if self.was_paused:
                    paused_for = time.time() - self.pause_started_at if self.pause_started_at else 0
                    self.start_time += paused_for
                    self.Play.time_since_detections["player"] = time.time()
                    self.Play.time_since_detections["enemy"] = time.time()
                    self.Play.time_since_player_last_found = time.time()
                    self.Play.time_since_last_proceeding = time.time()
                    self.last_processed_frame_id = -1
                    self.was_paused = False
                    self.pause_started_at = None
                    print("Bot resumed.")
                return False

            if not self.was_paused:
                self.window_controller.keys_up(list("wasd"))
                self.Play.reset_match_control_state()
                self.was_paused = True
                self.pause_started_at = time.time()
                print("Bot paused.")
            time.sleep(0.1)
            return True

        def main(self): #this is for timer to stop after time
            s_time = time.time()
            c = 0
            while True:
                if self.handle_pause_control():
                    s_time = time.time()
                    c = 0
                    continue
                if self.max_ips:
                    frame_start = time.perf_counter()
                if self.run_for_minutes > 0 and not self.in_cooldown:
                    elapsed_time = (time.time() - self.start_time) / 60
                    if elapsed_time >= self.run_for_minutes:
                        if self.state != "match":
                            cprint(f"timer is done, {self.run_for_minutes} minutes are over and bot is not in game. stopping bot fully", "#AAE5A4")
                            break
                        cprint(f"timer is done, {self.run_for_minutes} is over. continuing for 3 minutes if in game", "#AAE5A4")
                        self.in_cooldown = True # tries to finish game if in game
                        self.cooldown_start_time = time.time()
                        self.Stage_manager.states['lobby'] = lambda: 0

                if self.in_cooldown:
                    if time.time() - self.cooldown_start_time >= self.cooldown_duration:
                        cprint("stopping bot fully", "#AAE5A4")
                        break

                if abs(s_time - time.time()) > 1:
                    elapsed = time.time() - s_time
                    if elapsed > 0 and not self.visual_debug:
                        current_ips = c / elapsed
                        self.ips_ema = current_ips if self.ips_ema is None else (self.ips_ema * 0.75 + current_ips * 0.25)
                        print(f"{self.ips_ema:.2f} IPS")
                        if self.ips_ema < 3 and time.time() - self.low_frame_fps_warning_time > 20:
                            _, last_frame_time = self.window_controller.get_latest_frame()
                            frame_age = time.time() - last_frame_time if last_frame_time else 0
                            print(
                                "Low IPS with low CPU usually means the emulator/scrcpy feed is slow. "
                                f"Latest frame age: {frame_age:.1f}s. "
                                "Run: python tools/performance_check.py"
                            )
                            self.low_frame_fps_warning_time = time.time()
                    s_time = time.time()
                    c = 0

                try:
                    frame = self.window_controller.screenshot()
                except ConnectionError as e:
                    print(f"{e} Recovering scrcpy feed.")
                    self.handle_stale_scrcpy_feed()
                    continue

                _, last_ft = self.window_controller.get_latest_frame()
                if last_ft > 0 and (time.time() - last_ft) > self.window_controller.FRAME_STALE_TIMEOUT:
                    self.handle_stale_scrcpy_feed(last_ft)
                    continue

                self.stale_feed_recovery_attempts = 0

                frame_id = self.window_controller.get_latest_frame_id()
                if frame_id == self.last_processed_frame_id:
                    time.sleep(0.01)
                    continue
                self.last_processed_frame_id = frame_id

                self.manage_time_tasks(frame)

                if self.handle_visual_freeze(frame):
                    continue

                if self.state == "match" and time.time() < self.match_ready_at:
                    self.window_controller.keys_up(list("wasd"))
                    time.sleep(0.05)
                    continue

                brawler = self.Stage_manager.brawlers_pick_data[0]['brawler']
                self.Play.main(frame, brawler, self)
                c += 1

                if self.max_ips:
                    target_period = 1 / self.max_ips
                    work_time = time.perf_counter() - frame_start
                    if work_time < target_period:
                        time.sleep(target_period - work_time)

            self.control_window.close()

    main = Main()
    main.main()


all_brawlers = get_brawler_list()
if api_base_url != "localhost":
    update_missing_brawlers_info(all_brawlers)
    check_version()
    update_wall_model_classes()
    if not current_wall_model_is_latest():
        print("New Wall detection model found, downloading... (this might take a few minutes depending on your internet speed)")
        get_latest_wall_model_file()

# Use the smaller ratio to maintain aspect ratio
app = App(login, SelectBrawler, pyla_main, all_brawlers, Hub)
app.start(pyla_version, get_latest_version)
