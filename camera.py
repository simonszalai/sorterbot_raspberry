import os
import boto3
from picamera import PiCamera
from time import sleep

# Instantiate Pi Camera
camera = PiCamera()

# Set framerate to enable max resolution
camera.framerate = 15

# Set resoluton to maximum
camera.resolution = (2592, 1944)

# Start preview to give the camera time to adjust the light
camera.start_preview()
print("Camera started...")
sleep(2)
print("Taking picture...")
camera.capture("/home/pi/Desktop/image8.jpg")
print("Camera shutting down...")
camera.stop_preview()

# Instantiate AWS s3
s3 = boto3.resource("s3")

# Upload file
print("Uploading file to s3...")
s3.Bucket("sorterbot").upload_file("/home/pi/Desktop/image8.jpg", "image8.jpg")
print("File uploaded!")

# Delete file
os.remove("/home/pi/Desktop/image8.jpg")
print("Local file deleted!")
