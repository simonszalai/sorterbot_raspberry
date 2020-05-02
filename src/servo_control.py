"""
Contains the lower level insturctions that are manipulating the servos directly. These functions are called from
the high level counterpart, arm_control.

"""

import math
import pigpio
import concurrent.futures
from time import sleep


class ServoControl:
    def __init__(self, servos=(14, 15, 18, 24, 25), start_positions=(1425, 500, 1800, 1780, 1150)):
        """
        Contains the low level instructions to manipulate the servos using PWM (pulse width modulation). PiGPIO library is used instead of the
        default RPi.GPIO, because PiGPIO uses hardware timing which results in much more accurate pulse widths. Using software timing might delay and alter
        the pulses in case the CPU of the Raspberry Pi is doing some other work in the same time (like uploading a video, etc.).
        There are different speeds specified in the __init__ function. The units of these are pulse width change per second. A much slower speed is needed
        for recording the dataset video, since if the arm if moved to fast, the camera will resonate too much and the video will be blurred.

        Parameters
        ----------
        servos : tuple
            Tuple containing the GPIO numbers of the pins on the Raspberry Pi. Note that the Raspberry Pi have 2 different systems for numbering the pins:
            BOARD and BCM. BOARD uses the actual pin numbers and BCM uses the GPIO ID's. Here GPIO ID's are used. If you want to use a different system, it can
            be changed, depending on the library used, but in case of RPi.GPIO, the following function does that: GPIO.setmode(GPIO.BOARD) or
            GPIO.setmode(GPIO.BCM). Libraries usually default to BCM.
        start_positions : tuple
            Tuple containing the start positions for each servo. The units are in microseconds of pulse width that can be directly sent to the servos.
            Normally servos operate on a 50 Hz pulse cycle, which means that one cycle is 20ms long. If out of this 20ms, the signal is
            1.5ms (1500 microsec) long, the servo will move to neutral position and hold the shaft there. If the pulse width is less than that,
            it will move counter-clockwise as fast as it can. Usually (depends on the servo), a pulse width of 0.5ms corresponds to the farthest
            it can move counter-clockwise, while 2.5ms corresponds to the farthest clockwise. This means that here the values that correnspond
            to the neutral position of the arm should be suppliad, withing the range of (500, 2500).

        """

        self.pi = pigpio.pi()
        self.servos = servos
        self.start_positions = start_positions
        self.curr_positions = list(self.start_positions)
        self.speeds = {
            "dataset": 20,
            "fast": 700
        }

    def init_arm_position(self, is_inference=False):
        """
        Instructs the arm to move to inital position for taking a video for training or for taking pictures for inference.

        """

        axis_0_init_pos = 2200
        if is_inference:
            axis_0_init_pos = 2000

        self.execute_commands(((2, 1810),))
        self.execute_commands((
            (0, axis_0_init_pos),
            (1, 1200),
            (3, self.start_positions[3]),
            (4, self.start_positions[4])
        ), parallel=True)

    def execute_commands(self, commands, parallel=False):
        """
        Executes the commands supplied.

        Parameters
        ----------
        commands : tuple
            Each element in the tuple is one command, which is another tuple, including the polar coordinates the destination. The first element corrensponds
            to the pulse_width which servo0 needs to receive in order to move to the correct position, and the second element corrensponds to the distance
            in pixels from the top of the picture used for inference.
        parallel : bool
            If this parameter is true, the commands are executed simultaneously, utilizing multi-threading. This results in faster and smoother movement,
            but not always applicable. For example after picking up an object, the arm need to move further up to avoid accidentally bumping into other objects
            when moving sideways.

        """

        if parallel:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(commands))
            for cmd in commands:
                executor.submit(self.execute_command, cmd=cmd)
            executor.shutdown(wait=True)  # Wait for every thread to complete
        else:
            for cmd in commands:
                self.execute_command(cmd=cmd)

    def move_to_position(self, end_pos, is_container=False):
        """
        Instructs the arm to move to the supplied destination. On the first run, it fixes servo2 and servo3 to avoid unexpected
        movements. It always start with moving servo2 to position in order to avoid bouncing into objects. The variables servo_2_pos and servo_3_pos
        are functions of servo_1_pos and were determined by recording 7 datapoints of the servo angles for correct position for item pickup, then
        polynomial curves were fitted, which gave the constants used below.

        Parameters
        ----------
        end_pos : tuple
            A tuple containing the polar coordinates of the object. The first element corresponds to the pulse_width which servo0 needs to receive in order
            to move to the correct position, and the second element corrensponds to the distance in pixels from the top of the picture used for inference.
        is_container : bool
            If it is true, the arm will move to a higher position, which is suitable for dropping off an object.

        """

        height_offset = 300 if is_container else 0

        servo_1_pos = end_pos[1] - height_offset
        servo_2_pos = -7.83e-7 * servo_1_pos ** 3 + 5.26e-3 * servo_1_pos ** 2 - 10.3 * servo_1_pos + 7341 + height_offset
        servo_3_pos = 1.48e-6 * servo_1_pos ** 3 - 8.11e-3 * servo_1_pos ** 2 + 14.2 * servo_1_pos - 6634

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
        """
        Executes a single command on a single servo. Since servos move as fast as they can to the given position,
        which results in a too fast and unstable movement, instead of immediatly giving the command to move to the final positions,
        a series of intermediate positions are generated and supplied to the servo in a certain frequency to slow and smooth the movement.
        Except when recording the dataset (where even periods between movements are important) a sine smoothing is applied to further
        slow the movement at the beginning and end of every command. In order the achieve this, first a trajectory is generated as a list
        of intermediate positions, then the trajectory is executed by sendin each position to the servo and pausing for a short time
        between the steps.

        Parameters
        ----------
        cmd : tuple
            Tuple containing the command to be executed. cmd[0] is the servo index (not pin number!), which retrieves the pin number from the
            servos parameter of the __init__ function. cmd[1] is the pulse width where the servo should move, and cmd[2] is optionally the
            desired speed of the movement. It has to be one of the keys from self.speeds. If nothing is supplied, defaults to "fast".
            Used to slow down movement when recording training video.

        """

        servo_idx, end = cmd[0], cmd[1]
        servo = self.servos[servo_idx]
        start = self.curr_positions[servo_idx]

        # Try to get speed from command and default to "fast" if it's not possible. This also determines if this command is doing
        # dataset recording, since speed is only set explicitly in that case.
        dataset_recording = False
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

        # If start and end are too close to each other, no valid trajectory can be generated, so fix it in starting position.
        try:
            delta_angle_per_step = delta_angle / steps
        except ZeroDivisionError:
            self.pi.set_servo_pulsewidth(servo, start)
            return

        # Generate trajectory
        trajectory = []
        for step in range(int(steps) + 1):
            # Calculate movement delta for current step
            linear_delta = step * delta_angle_per_step

            # Apply sine smoothing
            sine_delta = math.sin(0.25 * linear_delta * math.pi / (0.25 * delta_angle) - 0.5 * math.pi) * delta_angle / 2 + (delta_angle / 2)

            # Calculate end positions for linear and sine smoothed cases
            linear_value = start + linear_delta
            sine_value = start + sine_delta

            # Append the appropriate value depending if a dataset recording is being done or a regular movement
            trajectory.append(linear_value if dataset_recording else sine_value)

        # Execute trajectory
        for step in trajectory:
            self.pi.set_servo_pulsewidth(servo, step)
            if sleep_length > 0:
                sleep(sleep_length)  # Sleep between steps to slow down movement

        # Update the current position with the last step of the trajectory
        self.curr_positions[servo_idx] = trajectory[-1]

    def neutralize_servos(self):
        """
        Neutralizes servos, which means that it sends a 0 pulse width to each of them, which will make them release the shafts,
        so they become moveable with hand.

        """

        for servo in self.servos:
            self.pi.set_servo_pulsewidth(servo, 0)
