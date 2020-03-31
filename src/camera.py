from picamera import PiCamera
from time import sleep


class Camera:
    def __init__(self):
        self.camera = PiCamera()
        self.camera.resolution = (1640, 1232)
        self.camera.framerate = 30

    def start(self, path):
        self.camera.start_recording(path)

    def stop(self):
        self.camera.stop_recording()

    def take_picture(self, path):
        self.camera.start_preview()
        sleep(0.5)
        self.camera.capture(path)
        self.camera.stop_preview()
