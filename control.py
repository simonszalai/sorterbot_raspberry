import pigpio
import time
import math

"""
GPIO 16: SERVO0, (L)2400-(R)700
GPIO 20: SERVO1, 900-2150
GPIO 21: SERVO2, 1800-1000
"""

servo0PIN = 36  # GPIO16
servo1PIN = 38  # GPIO20
servo2PIN = 40  # GPIO21

pi = pigpio.pi()


def generate_trajectory(servo, start, end, speed, smooth=True):
    delta_angle = end - start
    duration = abs(delta_angle) / speed
    steps = int(50 * duration)

    try:
        delta_angle_per_step = delta_angle / steps
    except ZeroDivisionError:
        pi.set_servo_pulsewidth(servo, end)
        return []

    trajectory = []
    # +1 to include 'end'
    for step in range(steps + 1):
        linear_value = step * delta_angle_per_step
        sine_value = math.sin(0.25 * linear_value * math.pi / (0.25 * delta_angle) - 0.5 * math.pi) * delta_angle / 2 + (delta_angle / 2)
        trajectory.append(int(start + sine_value if smooth else linear_value))

    return trajectory


def execute_trajectory(servo, trajectory):
    for step in trajectory:
        t0 = time.time()
        pi.set_servo_pulsewidth(servo, step)
        t1 = time.time()
        print("t1", ((t1 - t0) * 1000))
        time.sleep((1 / 50) - (t1 - t0))
        t2 = time.time()
        print("t2", (t2 - t1) * 1000)
        print('total', (t2 - t0) * 1000)


pi.set_servo_pulsewidth(16, 0)
pi.set_servo_pulsewidth(20, 0)
pi.set_servo_pulsewidth(21, 0)

start = {
    16: 1550,
    20: 500,
    21: 1800
}

while True:
    servo = int(input("Servo: "))
    end = int(input("Pulse Width: "))

    trajectory = generate_trajectory(servo=servo, start=start[servo], end=end, speed=200)
    print(trajectory)
    execute_trajectory(servo, trajectory)

    if end is not None:
        start[servo] = end

    time.sleep(0.5)
