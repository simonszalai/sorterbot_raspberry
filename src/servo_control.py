import os
import re
import pigpio
import time
import math
from pathlib import Path
from datetime import datetime
from video import Camera

"""
GPIO 16: SERVO0, (L)2400-(R)550 // 550 = -90deg, 1450 = 0deg, 2350 = +90deg
GPIO 20: SERVO1, 900-2150
GPIO 21: SERVO2, 1800-1000
"""


class ServoControl:
    def __init__(self):
        self.pi = pigpio.pi()
        self.camera = Camera()
        self.servos = (16, 20, 21)
        self.current_set_path = self.create_next_folder()
        self.start_positions = {
            self.servos[0]: 1425,
            self.servos[1]: 500,
            self.servos[2]: 1800
        }
        self.speeds = {
            "slow": 25,
            "fast": 500
        }

    def execute_commands(self, commands):
        for cmd in commands:
            servo, end_position = cmd[0], cmd[1]
            try:
                speed = self.speeds[cmd[2]]
            except IndexError:
                speed = self.speeds["fast"]
            self.move_arm(servo=servo, start=self.start_positions[servo], end=end_position, speed=speed)

    def init_arm_for_recording(self):
        self.execute_commands(((self.servos[0], 2200), (self.servos[2], 1810), (self.servos[1], 1200)))

    def reset_arm(self):
        self.execute_commands(((self.servos[0], 1425), (self.servos[1], 500)))

    def do_recording(self):
        self.camera.start(path=os.path.join(self.current_set_path, datetime.now().strftime("%d.%m.%Y_%H:%M:%S") + ".h264"))
        self.execute_commands([(self.servos[0], 800, "slow")])
        self.camera.stop()
        self.init_arm_for_recording()

    def move_arm(self, servo, start, end, speed=1, freq=50, dataset_recording=False):
        delta_angle = end - start
        duration = abs(delta_angle) / speed
        steps = abs(freq * duration)
        try:
            delta_angle_per_step = delta_angle / steps
        except ZeroDivisionError:
            return []

        trajectory = []
        for step in range(int(steps) + 1):
            linear_delta = step * delta_angle_per_step
            sine_delta = math.sin(0.25 * linear_delta * math.pi / (0.25 * delta_angle) - 0.5 * math.pi) * delta_angle / 2 + (delta_angle / 2)
            linear_value = start + linear_delta
            sine_value = start + sine_delta
            trajectory.append(linear_value if dataset_recording else sine_value)

        for step in trajectory:
            t0 = time.time()
            self.pi.set_servo_pulsewidth(servo, step)
            t1 = time.time()
            sleep_length = (1 / freq) - (t1 - t0)
            if sleep_length > 0:
                time.sleep(sleep_length)

        self.start_positions[servo] = trajectory[-1]

    def create_next_folder(self):
        recordings_path = os.path.join(Path().parent.absolute(), "recordings")

        # List contents of recordings folder or create it if it does not exist
        folder_names = []
        try:
            folder_names = [f.name for f in os.scandir(recordings_path) if f.is_dir()]
        except FileNotFoundError:
            os.mkdir(recordings_path)
            next_folder = os.path.join(recordings_path, "1")

        # Sort folder names
        def sorted_alphanumeric(data):
            convert = lambda text: int(text) if text.isdigit() else text.lower()
            alphanum_key = lambda key: [convert(c) for c in re.split('([0-9]+)', key)]
            return sorted(data, key=alphanum_key)
        folder_names = sorted_alphanumeric(folder_names)

        # Check if there are any folders in recordings and initialize a folder with number 1 if not
        try:
            next_folder = os.path.join(recordings_path, folder_names[-1])
        except IndexError:
            next_folder = os.path.join(recordings_path, "1")
            os.mkdir(next_folder)

        # Check if last folder contains any items and create new folder if it does
        if len(os.listdir(next_folder)) != 0:
            next_folder = os.path.join(recordings_path, str(int(folder_names[-1]) + 1))
            os.mkdir(next_folder)

        return next_folder

    def close(self):
        if self.camera.camera.recording:
            self.camera.stop()
        self.reset_arm()
        for servo in self.servos:
            self.pi.set_servo_pulsewidth(servo, 0)


control = ServoControl()

while True:
    try:
        cmd = int(input("Command: "))
        if cmd == 0:
            control.close()
            break
        elif cmd == 1:
            control.init_arm_for_recording()
        elif cmd == 2:
            control.do_recording()
    except Exception as e:
        control.close()
        raise e

    time.sleep(0.5)
