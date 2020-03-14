import os
import pigpio
import time
import math
from pathlib import Path
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

        self.current_set_path = self.create_next_folder()

        self.servo0PIN = 36  # GPIO16
        self.servo1PIN = 38  # GPIO20
        self.servo2PIN = 40  # GPIO21

        self.start_positions = {
            16: 1450,
            20: 500,
            21: 1800
        }

        self.speeds = {
            "slow": 25,
            "fast": 500
        }

    def init_recording(self):
        trajectory_1 = self.generate_trajectory(start=self.start_positions[16], end=2200, speed=self.speeds["fast"])
        trajectory_2 = self.generate_trajectory(start=self.start_positions[20], end=1200, speed=self.speeds["fast"])
        trajectory_3 = self.generate_trajectory(start=self.start_positions[21], end=1810, speed=self.speeds["fast"])

        self.execute_trajectory(16, trajectory_1)
        self.execute_trajectory(21, trajectory_3)
        self.execute_trajectory(20, trajectory_2)

    def do_recording(self):
        trajectory_1 = self.generate_trajectory(start=self.start_positions[16], end=800, speed=self.speeds["slow"])
        self.camera.start()
        self.execute_trajectory(16, trajectory_1)
        self.camera.stop()
        self.init_recording()

    def generate_trajectory(self, start, end, speed=1, freq=50, dataset_recording=False):
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

        return trajectory

    def execute_trajectory(self, servo, trajectory, freq=50):
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
        try:
            folder_names = [f.name for f in os.scandir(recordings_path) if f.is_dir()]
        except FileNotFoundError:
            os.mkdir(recordings_path)
            next_folder = os.path.join(recordings_path, "1")

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

        print(next_folder)
        return next_folder

    def close(self):
        self.pi.set_servo_pulsewidth(16, 0)
        self.pi.set_servo_pulsewidth(20, 0)
        self.pi.set_servo_pulsewidth(21, 0)


control = ServoControl()

while True:
    try:
        cmd = int(input("Command: "))
        if cmd == 0:
            control.close()
            break
        elif cmd == 1:
            control.init_recording()
        elif cmd == 2:
            control.do_recording()
    except Exception:
        control.close()

    time.sleep(0.5)
