import time
import math
import pigpio
import concurrent.futures
from time import sleep

"""
GPIO 16: SERVO0, (L)2400-(R)550 // 550 = -90deg, 1450 = 0deg, 2350 = +90deg
GPIO 20: SERVO1, 900-2150
GPIO 21: SERVO2, 1800-1000
GPIO 26: SERVO3, 
"""


class ServoControl:
    def __init__(self):
        self.pi = pigpio.pi()
        self.servos = (14, 15, 18, 24)
        self.start_positions = (1425, 500, 1800, 1780,)
        self.curr_positions = [1425, 500, 1800, 1780]
        self.speeds = {
            "dataset": 20,
            "fast": 700
        }

    def init_arm_position(self, is_inference=False):
        axis_0_init_pos = 2200
        if is_inference:
            axis_0_init_pos = 2000

        self.execute_commands([(2, 1810)])
        self.execute_commands(((0, axis_0_init_pos), (1, 1200), (3, 1780)), parallel=True)

    def execute_commands(self, commands, parallel=False):
        if parallel:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(commands))
            for cmd in commands:
                executor.submit(self.execute_command, cmd=cmd)
            executor.shutdown(wait=True)  # Wait for every thread to complete
        else:
            for cmd in commands:
                self.execute_command(cmd=cmd)

    def move_to_position(self, end_pos, is_container=False):
        height_offset = 200 if is_container else 0
        servo_1_pos = ((end_pos[1] * -1 + 1232) / 1232 * 700) + 1100
        servo_2_pos = 8.99e-4 * servo_1_pos ** 2 - 2.46 * servo_1_pos + 2877 + height_offset
        servo_3_pos = 1.59e-6 * servo_1_pos ** 3 - 8.18e-3 * servo_1_pos ** 2 + 13.5 * servo_1_pos - 5847

        # To fix servos 2 and 3. It only does meaninful things at the first movement after
        # starting sequence, after that just fixes them on current movement.
        self.execute_commands((
            (2, self.curr_positions[2]),
            (3, self.curr_positions[3])
        ), parallel=True)

        self.execute_commands((
            (2, self.start_positions[2]),
        ))

        self.execute_commands((
            (1, servo_1_pos),
            (0, end_pos[0]),
        ), parallel=True)

        self.execute_commands((
            (2, servo_2_pos),
            (3, servo_3_pos)
        ), parallel=True)

    def execute_command(self, cmd):
        servo_idx, end = cmd[0], cmd[1]
        servo = self.servos[servo_idx]
        start = self.curr_positions[servo_idx]
        dataset_recording = False

        # Fix servo in starting position in case start and end are the same
        if start == end:
            self.pi.set_servo_pulsewidth(servo, start)

        try:
            speed = self.speeds[cmd[2]]
            if cmd[2] == "dataset":
                dataset_recording = True
        except IndexError:
            speed = self.speeds["fast"]

        rotation_units_per_sec = 2 if dataset_recording else 50
        sleep_length = 1 / 1.5 if dataset_recording else 1 / 50

        delta_angle = end - start
        duration = delta_angle / speed
        steps = abs(rotation_units_per_sec * duration)

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
                sleep(sleep_length)

        self.curr_positions[servo_idx] = trajectory[-1]

    def neutralize_servos(self):
        for servo in self.servos:
            self.pi.set_servo_pulsewidth(servo, 0)
