import asyncio
import time

import window_controller
from gui.hub import Hub
from gui.login import login
from gui.main import App
from gui.select_brawler import SelectBrawler
from lobby_automation import LobbyAutomation
from play import Play
from stage_manager import StageManager
from state_finder import get_state
from time_management import TimeManagement
from utils import load_toml_as_dict, current_wall_model_is_latest, api_base_url, extract_text_strings
from utils import get_brawler_list, update_missing_brawlers_info, check_version, async_notify_user, \
    update_wall_model_classes, get_latest_wall_model_file, get_latest_version, cprint
from window_controller import WindowController

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
            self.last_stale_feed_recovery = 0.0
            self.last_disconnect_check = 0.0
            self.disconnect_reload_attempts = 0
            self.last_processed_frame_id = -1

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

        def manage_time_tasks(self, frame):
            if self.handle_disconnect_screen(frame):
                return

            if self.Time_management.state_check():
                state = get_state(frame)
                self.state = state
                if state != "match":
                    self.Play.time_since_last_proceeding = time.time()
                frame_data = None
                self.Stage_manager.do_state(state, frame_data)

            if self.Time_management.no_detections_check():
                frame_data = self.Play.time_since_detections
                for key, value in frame_data.items():
                    if time.time() - value > self.no_detections_action_threshold:
                        self.restart_brawl_stars()

            if self.Time_management.idle_check():
                #print("check for idle!")
                self.lobby_automator.check_for_idle(frame)

        def handle_disconnect_screen(self, frame):
            if time.time() - self.last_disconnect_check < 3:
                return False
            self.last_disconnect_check = time.time()

            h, w = frame.shape[:2]
            center_crop = frame[int(h * 0.22):int(h * 0.50), int(w * 0.15):int(w * 0.65)]
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
                self.window_controller.restart_brawl_stars()
                self.disconnect_reload_attempts = 0
            else:
                self.window_controller.click(550, 450, already_include_ratio=False)
                time.sleep(3)
            return True

        def main(self): #this is for timer to stop after time
            s_time = time.time()
            c = 0
            while True:
                if self.max_ips:
                    frame_start = time.perf_counter()
                if self.run_for_minutes > 0 and not self.in_cooldown:
                    elapsed_time = (time.time() - self.start_time) / 60
                    if elapsed_time >= self.run_for_minutes:
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
                        print(f"{c / elapsed:.2f} IPS")
                    s_time = time.time()
                    c = 0

                frame = self.window_controller.screenshot()

                _, last_ft = self.window_controller.get_latest_frame()
                if last_ft > 0 and (time.time() - last_ft) > self.window_controller.FRAME_STALE_TIMEOUT:
                    self.Play.window_controller.keys_up(list("wasd"))
                    if time.time() - self.last_stale_feed_recovery > 30:
                        print("Stale scrcpy frame detected -- restarting scrcpy feed.")
                        self.last_stale_feed_recovery = time.time()
                        self.window_controller.restart_scrcpy_client()
                    else:
                        print("Stale frame detected, waiting for scrcpy recovery cooldown.")
                    continue

                frame_id = self.window_controller.get_latest_frame_id()
                if frame_id == self.last_processed_frame_id:
                    time.sleep(0.01)
                    continue
                self.last_processed_frame_id = frame_id

                self.manage_time_tasks(frame)


                brawler = self.Stage_manager.brawlers_pick_data[0]['brawler']
                self.Play.main(frame, brawler, self)
                c += 1

                if self.max_ips:
                    target_period = 1 / self.max_ips
                    work_time = time.perf_counter() - frame_start
                    if work_time < target_period:
                        time.sleep(target_period - work_time)

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
