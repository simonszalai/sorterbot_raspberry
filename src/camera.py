"""
This module controls the Raspberry Pi's camera, which is used to make training videos
and take inference pictures.

"""

from picamera import PiCamera
from time import sleep


class Camera:
    def __init__(self, resolution=(1640, 1232), framerate=30):
        """
        This class includes the methods to record video and take a picture.

        Parameters
        ----------
        resolution : tuple
            Resolution of the video/picture to be taken. Follows the format: (width, heigh).
            1640*1232 is the heighest resolution that still includes the maximum field of view.

        framerate : int
            Frames per second to be recorded when taking a training video. Higher framerate results in
            less blurred video and training pictures. The camera supports 40 fps at this resoluton, but
            the h264 codec cannot handle it, so 30 needs to be used here.

        """

        self.camera = PiCamera()
        self.camera.resolution = resolution
        self.camera.framerate = framerate

    def start(self, path):
        """
        Start video recording.

        """

        self.camera.start_recording(path)

    def stop(self):
        """
        Stop video recording.

        """

        self.camera.stop_recording()

    def take_picture(self, path):
        """
        Take inference picture and save it to disk.

        Parameters
        ----------
        path : str
            Path where the taken image should be saved.

        """

        self.camera.start_preview()
        sleep(0.5)
        self.camera.capture(path)
        self.camera.stop_preview()
