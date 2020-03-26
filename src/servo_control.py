import os
import time
import math
import pigpio
import concurrent.futures
from datetime import datetime
from camera import Camera
from storage import Storage
from time import sleep

"""
GPIO 16: SERVO0, (L)2400-(R)550 // 550 = -90deg, 1450 = 0deg, 2350 = +90deg
GPIO 20: SERVO1, 900-2150
GPIO 21: SERVO2, 1800-1000
"""


class ServoControl:
    def __init__(self):
        self.pi = pigpio.pi()
        self.camera = Camera()
        self.storage = Storage()
        self.servos = (16, 20, 21)
        self.current_set_path = self.storage.create_next_train_folder()
        self.start_positions = {
            self.servos[0]: 1425,
            self.servos[1]: 500,
            self.servos[2]: 1800
        }
        self.speeds = {
            "dataset": 25,
            "fast": 700
        }

    def init_arm_position(self, is_inference):
        axis_0_init_pos = 2200
        if is_inference:
            axis_0_init_pos = 2000

        self.execute_commands_series([(self.servos[2], 1810)])
        self.execute_commands_parallel(((self.servos[0], axis_0_init_pos), (self.servos[1], 1200)))

    def reset_arm(self):
        self.execute_commands_parallel(((self.servos[0], 1425), (self.servos[1], 500)))

    def do_recording(self):
        video_path = os.path.join(self.current_set_path, datetime.now().strftime("%d.%m.%Y_%H:%M:%S") + ".h264")
        self.camera.start(path=video_path)
        self.execute_commands_series([(self.servos[0], 800, "dataset")])
        self.camera.stop()
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        executor.submit(self.storage.upload_file, "sorterbot-training-videos", video_path)
        executor.submit(self.init_arm_position)

    def take_pictures(self):
        # Construct session path
        curr_sess_path = self.storage.create_next_session_folder()

        # Init arm position for inference
        self.init_arm_position(is_inference=True)

        # Upload files on separate threads so the arm's movement is not blocked until upload is complete
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # Generate positions where pictures will be takes
        steps = reversed(range(1000, 2200, 200))
        for step in steps:
            print(step)
            # Construct image path
            image_path = os.path.join(curr_sess_path, f"{step}.jpg")

            # Move arm to next position
            self.execute_commands_series([(self.servos[0], step)])

            # Wait a bit for stabilization
            sleep(0.5)

            # Take the picture
            self.camera.take_picture(image_path)

            # Upload it to S3
            executor.submit(self.storage.upload_file, "sorterbot", image_path)

        # Move arm to initial position
        self.reset_arm()

    def execute_commands_series(self, commands):
        for cmd in commands:
            self.move_arm(cmd=cmd)

    def execute_commands_parallel(self, commands):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(commands))
        for cmd in commands:
            executor.submit(self.move_arm, cmd=cmd)

    def move_arm(self, cmd):
        servo, end = cmd[0], cmd[1]
        start = self.start_positions[servo]
        dataset_recording = False

        try:
            speed = self.speeds[cmd[2]]
            if cmd[2] == "dataset":
                dataset_recording = True
        except IndexError:
            speed = self.speeds["fast"]

        steps_per_sec = 2 if dataset_recording else 50
        sleep_length = 1 / 1.5 if dataset_recording else 1 / 50

        delta_angle = end - start
        duration = delta_angle / speed
        steps = abs(steps_per_sec * duration)

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
            self.pi.set_servo_pulsewidth(servo, step)
            if sleep_length > 0:
                time.sleep(sleep_length)

        self.start_positions[servo] = trajectory[-1]

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
            control.init_arm_position()
        elif cmd == 2:
            control.do_recording()
        elif cmd == 3:
            control.take_pictures()
    except Exception as e:
        control.close()
        raise e

    time.sleep(0.5)
