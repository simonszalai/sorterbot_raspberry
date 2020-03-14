import os
import boto3
from picamera import PiCamera
from time import sleep


class Camera:
    def __init__(self):
        self.camera = PiCamera()
        self.camera.resolution = (1920, 1080)
        self.camera.framerate = 30

    def start(self, path):
        self.camera.start_recording(path)

    def stop(self):
        self.camera.stop_recording()
