import atexit
import math
import socket
import threading
import time
import cv2
from typing import List

import scrcpy
from adbutils import adb

from utils import load_toml_as_dict

# --- Configuration ---
brawl_stars_width, brawl_stars_height = 1920, 1080

key_coords_dict = {
    "H": (1400, 990),
    "G": (1640, 990),
    "M": (1725, 800),
    "Q": (1660, 980),
    "E": (1510, 880),
    "F": (1360, 920),
}

directions_xy_deltas_dict = {
    "w": (0, -150),
    "a": (-150, 0),
    "s": (0, 150),
    "d": (150, 0),
}

BRAWL_STARS_PACKAGE = load_toml_as_dict("cfg/general_config.toml")["brawl_stars_package"]

EMULATOR_PORTS = {
    "BlueStacks": [5555, 5556, 5557, 5565],
    "LDPlayer": [5555, 5557, 5559, 5554],
    "MEmu": [21503, 21513, 21523, 5555],
    "MuMu": [16384, 16416, 16448, 7555, 5558, 5557, 5556, 5555, 5554],
    "Others": [5555, 5558, 7555, 16384, 16416, 16448, 21503, 5635],
}


def _unique_ports(ports):
    unique = []
    for port in ports:
        try:
            port = int(port)
        except (TypeError, ValueError):
            continue
        if port == 5037:
            continue
        if port not in unique:
            unique.append(port)
    return unique


def _is_port_open(host, port, timeout=0.05):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except OSError:
        return False


def _serial_port(serial):
    if serial.startswith("emulator-"):
        try:
            return int(serial.rsplit("-", 1)[1])
        except ValueError:
            return None
    if ":" in serial:
        try:
            return int(serial.rsplit(":", 1)[1])
        except ValueError:
            return None
    return None


class WindowController:
    def __init__(self):
        self.scale_factor = None
        self.width = None
        self.height = None
        self.width_ratio = None
        self.height_ratio = None
        self.joystick_x, self.joystick_y = None, None
        # --- 2. ADB & Scrcpy Connection ---
        print("Connecting to ADB...")
        try:
            def list_online_devices():
                devices = []
                for dev in adb.device_list():
                    try:
                        state = dev.get_state()
                    except Exception:
                        state = "unknown"
                    if state == "device":
                        devices.append(dev)
                    else:
                        print(f"Skipping ADB device {dev.serial} (state: {state})")
                return devices

            def prefer_selected_devices(devices, selected_emulator, configured_port):
                preferred_ports = set(_unique_ports([configured_port] + EMULATOR_PORTS.get(selected_emulator, [])))
                preferred_serials = {f"127.0.0.1:{port}" for port in preferred_ports}
                return [
                    dev for dev in devices
                    if _serial_port(dev.serial) in preferred_ports or dev.serial in preferred_serials
                ]

            general_config = load_toml_as_dict("cfg/general_config.toml")
            selected_emulator = general_config.get("current_emulator", "Others")
            configured_port = general_config.get("emulator_port", 0)
            self.scrcpy_max_fps = int(general_config.get("scrcpy_max_fps", 15))
            if self.scrcpy_max_fps <= 0:
                self.scrcpy_max_fps = None
            candidate_ports = _unique_ports(
                [configured_port]
                + EMULATOR_PORTS.get(selected_emulator, EMULATOR_PORTS["Others"])
                + EMULATOR_PORTS["Others"]
                + list(range(5565, 5756, 10))
            )

            device_list = list_online_devices()
            preferred_devices = prefer_selected_devices(device_list, selected_emulator, configured_port)

            # Probe selected/common emulator ports quickly before calling adb.connect.
            # If nothing is online yet, fall back to the full candidate list so
            # generic "Others" setups still have a chance. Port 5037 is filtered
            # out by _unique_ports because it is the ADB server port.
            if not preferred_devices and (selected_emulator != "Others" or not device_list):
                ports_to_try = [port for port in candidate_ports if _is_port_open("127.0.0.1", port)]
                if not ports_to_try and not device_list:
                    ports_to_try = candidate_ports
                for port in ports_to_try:
                    try:
                        adb.connect(f"127.0.0.1:{port}")
                    except Exception:
                        pass
                device_list = list_online_devices()
                preferred_devices = prefer_selected_devices(device_list, selected_emulator, configured_port)

            if not device_list:
                tried_ports = ", ".join(str(port) for port in candidate_ports)
                raise ConnectionError(f"No online ADB devices found. Tried ports: {tried_ports}")

            self.device = preferred_devices[0] if preferred_devices else device_list[0]
            if selected_emulator != "Others" and not preferred_devices:
                print(
                    f"Could not identify a {selected_emulator} device by port; "
                    f"using first online ADB device instead."
                )
            print(f"Connected to {selected_emulator}: {self.device.serial}")

            self.frame_lock = threading.Lock()
            self.scrcpy_client = None
            self.last_frame = None
            self.last_frame_time = 0.0
            self.frame_id = 0
            self.last_stale_warning_time = 0.0
            self.last_joystick_pos = (None, None)
            self.last_joystick_down_time = 0.0
            self.FRAME_STALE_TIMEOUT = 15.0
            self.start_scrcpy_client()
            atexit.register(self.close)
            print("Scrcpy client started successfully.")

        except Exception as e:
            raise ConnectionError(f"Failed to initialize Scrcpy: {e}")
        self.are_we_moving = False
        self.PID_JOYSTICK = 1  # ID for WASD movement
        self.PID_ATTACK = 2  # ID for clicks/attacks
        self.check_if_brawl_stars_crashed_timer = load_toml_as_dict("cfg/time_tresholds.toml")["check_if_brawl_stars_crashed"]
        self.time_since_checked_if_brawl_stars_crashed = time.time()

    def start_scrcpy_client(self):
        def on_frame(frame):
            if frame is not None:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                with self.frame_lock:
                    self.last_frame = frame
                    self.last_frame_time = time.time()
                    self.frame_id += 1

        with self.frame_lock:
            self.last_frame = None
            self.last_frame_time = 0.0
            self.frame_id = 0
            self.last_stale_warning_time = 0.0
        self.are_we_moving = False
        self.last_joystick_pos = (None, None)
        self.last_joystick_down_time = 0.0

        client_kwargs = {"device": self.device, "max_width": 0}
        if self.scrcpy_max_fps:
            client_kwargs["max_fps"] = self.scrcpy_max_fps
        self.scrcpy_client = scrcpy.Client(**client_kwargs)
        self.scrcpy_client.add_listener(scrcpy.EVENT_FRAME, on_frame)
        self.scrcpy_client.start(threaded=True)

    def restart_scrcpy_client(self):
        print("Restarting scrcpy client...")
        old_client = self.scrcpy_client
        self.scrcpy_client = None
        if old_client is not None:
            def stop_old_client():
                try:
                    old_client.stop()
                except Exception as e:
                    print(f"Could not stop old scrcpy client cleanly: {e}")

            stop_thread = threading.Thread(target=stop_old_client, daemon=True)
            stop_thread.start()
            stop_thread.join(timeout=2)
            if stop_thread.is_alive():
                print("Old scrcpy client did not stop within 2s; starting a new client anyway.")
        time.sleep(0.4)
        self.start_scrcpy_client()
        print("Scrcpy client restarted successfully.")

    def get_latest_frame(self):
        with self.frame_lock:
            if self.last_frame is None:
                return None, 0.0
            return self.last_frame, self.last_frame_time

    def get_latest_frame_id(self):
        with self.frame_lock:
            return self.frame_id

    def restart_brawl_stars(self):
        self.device.app_stop(BRAWL_STARS_PACKAGE)
        time.sleep(1)
        self.device.app_start(BRAWL_STARS_PACKAGE)
        time.sleep(3)
        self.time_since_checked_if_brawl_stars_crashed = time.time()
        print("Brawl stars restarted successfully.")

    def screenshot(self):
        c_time = time.time()
        if c_time - self.time_since_checked_if_brawl_stars_crashed > self.check_if_brawl_stars_crashed_timer:
            opened_app = self.device.app_current().package.strip()
            if opened_app != BRAWL_STARS_PACKAGE.strip():
                print(f"Brawl stars has crashed, {opened_app} is the app opened ! Restarting...")
                self.device.app_start(BRAWL_STARS_PACKAGE)
                time.sleep(3)
                self.time_since_checked_if_brawl_stars_crashed = time.time()
            else:
                self.time_since_checked_if_brawl_stars_crashed = c_time
        frame, frame_time = self.get_latest_frame()

        deadline = time.time() + 15
        while frame is None:
            if time.time() > deadline:
                raise ConnectionError(
                    "No frame received from scrcpy within 15s. "
                    "Check USB/emulator connection."
                )
            print("Waiting for first frame...")
            time.sleep(0.1)
            frame, frame_time = self.get_latest_frame()

        age = time.time() - frame_time
        if frame_time > 0 and age > self.FRAME_STALE_TIMEOUT:
            if time.time() - self.last_stale_warning_time > 2:
                print(f"WARNING: scrcpy frame is {age:.1f}s stale -- feed may be frozen")
                self.last_stale_warning_time = time.time()


        if not self.width or not self.height:
            self.width = frame.shape[1]
            self.height = frame.shape[0]
            if (self.width, self.height) != (brawl_stars_width, brawl_stars_height):
                print(f"⚠️⚠️⚠️Unexpected resolution: {self.width}x{self.height}. Expected {brawl_stars_width}x{brawl_stars_height}. Please set your emulator resolution to 1920x1080 for best results.")
            self.width_ratio = self.width / brawl_stars_width
            self.height_ratio = self.height / brawl_stars_height
            self.joystick_x, self.joystick_y = 220 * self.width_ratio, 870 * self.height_ratio
            self.scale_factor = min(self.width_ratio, self.height_ratio)

        return frame
    def touch_down(self, x, y, pointer_id=0):
        # We explicitly pass the pointer_id
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_DOWN, pointer_id)

    def touch_move(self, x, y, pointer_id=0):
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_MOVE, pointer_id)

    def touch_up(self, x, y, pointer_id=0):
        self.scrcpy_client.control.touch(int(x), int(y), scrcpy.ACTION_UP, pointer_id)

    def move_joystick_angle(self, angle_degrees: float, radius: float = 150.0):
        """Move the joystick in an exact direction given by angle_degrees.

        0° = right, 90° = down, 180° = left, 270° = up (screen coordinates).
        radius controls how far from center the touch point is placed.
        """
        angle_rad = math.radians(angle_degrees)
        scaled_radius = radius * self.scale_factor
        target_x = self.joystick_x + math.cos(angle_rad) * scaled_radius
        target_y = self.joystick_y + math.sin(angle_rad) * scaled_radius

        joystick_needs_refresh = time.time() - self.last_joystick_down_time > 2.0
        if self.are_we_moving and joystick_needs_refresh:
            self.stop_joystick()

        if not self.are_we_moving:
            self.touch_down(self.joystick_x, self.joystick_y, pointer_id=self.PID_JOYSTICK)
            self.are_we_moving = True
            self.last_joystick_down_time = time.time()
            self.last_joystick_pos = (target_x, target_y)
            self.touch_move(target_x, target_y, pointer_id=self.PID_JOYSTICK)
        elif self.last_joystick_pos != (target_x, target_y):
            self.touch_move(target_x, target_y, pointer_id=self.PID_JOYSTICK)
            self.last_joystick_pos = (target_x, target_y)

    def stop_joystick(self):
        """Release the joystick touch."""
        if self.are_we_moving:
            try:
                self.touch_up(self.joystick_x, self.joystick_y, pointer_id=self.PID_JOYSTICK)
            except Exception as e:
                print(f"Could not release joystick cleanly: {e}")
            self.are_we_moving = False
            self.last_joystick_down_time = 0.0
            self.last_joystick_pos = (None, None)

    def keys_up(self, keys: List[str]):
        if "".join(keys).lower() == "wasd":
            self.stop_joystick()

    def keys_down(self, keys: List[str]):

        delta_x, delta_y = 0, 0
        for key in keys:
            if key in directions_xy_deltas_dict:
                dx, dy = directions_xy_deltas_dict[key]
                delta_x += dx
                delta_y += dy

        joystick_needs_refresh = time.time() - self.last_joystick_down_time > 2.0
        if self.are_we_moving and joystick_needs_refresh:
            self.stop_joystick()

        if not self.are_we_moving:
            self.touch_down(self.joystick_x, self.joystick_y, pointer_id=self.PID_JOYSTICK)
            self.are_we_moving = True
            self.last_joystick_down_time = time.time()
            self.last_joystick_pos = (self.joystick_x + delta_x, self.joystick_y + delta_y)

        if self.last_joystick_pos != (self.joystick_x + delta_x, self.joystick_y + delta_y):
            self.touch_move(self.joystick_x + delta_x, self.joystick_y + delta_y, pointer_id=self.PID_JOYSTICK)
            self.last_joystick_pos = (self.joystick_x + delta_x, self.joystick_y + delta_y)

    def click(self, x: int, y: int, delay=0.005, already_include_ratio=True, touch_up=True, touch_down=True):
        if not already_include_ratio:
            x = x * self.width_ratio
            y = y * self.height_ratio
        # Use PID_ATTACK for clicks so we don't interrupt movement
        if touch_down: self.touch_down(x, y, pointer_id=self.PID_ATTACK)
        time.sleep(delay)
        if touch_up: self.touch_up(x, y, pointer_id=self.PID_ATTACK)

    def press_key(self, key, delay=0.005, touch_up=True, touch_down=True):
        if key not in key_coords_dict:
            return
        x, y = key_coords_dict[key]
        target_x = x * self.width_ratio
        target_y = y * self.height_ratio
        self.click(target_x, target_y, delay, touch_up=touch_up, touch_down=touch_down)

    def swipe(self, start_x, start_y, end_x, end_y, duration=0.2):
        dist_x = end_x - start_x
        dist_y = end_y - start_y
        distance = math.sqrt(dist_x ** 2 + dist_y ** 2)

        if distance == 0:
            return

        step_len = 25
        steps = max(int(distance / step_len), 1)
        step_delay = duration / steps

        self.touch_down(int(start_x), int(start_y), pointer_id=self.PID_ATTACK)
        for i in range(1, steps + 1):
            t = i / steps
            cx = start_x + dist_x * t
            cy = start_y + dist_y * t
            time.sleep(step_delay)
            self.touch_move(int(cx), int(cy), pointer_id=self.PID_ATTACK)
        self.touch_up(int(end_x), int(end_y), pointer_id=self.PID_ATTACK)

    def close(self):
        if hasattr(self, 'scrcpy_client'):
            client = self.scrcpy_client
            self.scrcpy_client = None
            if client is not None:
                client.stop()
