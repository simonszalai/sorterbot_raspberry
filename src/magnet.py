"""
This module controls the magnet on the robotic arm which is used to pick up objects.
I Grove Electromagnet is used, which has it's own control electronic and can be turned
on and off by supplying a logical high and logical low signal to the appropriate input.

"""

import RPi.GPIO as GPIO


class MagnetControl:
    def __init__(self, pin=23):
        """
        This class includes methods to turn the magnet on and off.

        Parameters
        ----------
        pin : int
            GPIO number of the pin which is used to control the magnet.

        """

        self.pin = pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(self.pin, GPIO.OUT)

    def on(self):
        """
        Turns the magnet on.

        """

        GPIO.output(self.pin, GPIO.HIGH)

    def off(self):
        """
        Turns the magnet off.

        """

        GPIO.output(self.pin, GPIO.LOW)
