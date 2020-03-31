import os
import concurrent.futures
from time import sleep
from datetime import datetime

from camera import Camera
from storage import Storage
from magnet import MagnetControl
from servo_control import ServoControl


class ArmCommands:
    def __init__(self):
        self.camera = Camera()
        self.storage = Storage()
        self.sc = ServoControl()
        self.magnet = MagnetControl()

        self.current_set_path = self.storage.create_next_train_folder()

    def do_recording(self):
        video_path = os.path.join(self.current_set_path, datetime.now().strftime("%d.%m.%Y_%H:%M:%S") + ".h264")
        self.camera.start(path=video_path)
        self.sc.execute_commands(((0, 800, "dataset"),))
        self.camera.stop()

        # Don't wait for upload to finish before initializing the arm
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        executor.submit(self.storage.upload_file, "sorterbot-training-videos", video_path)
        executor.submit(self.sc.init_arm_position)

    def take_pictures(self):
        # Construct session path
        curr_sess_path = self.storage.create_next_session_folder()

        # Init arm position for inference
        self.sc.init_arm_position(is_inference=True)

        # Upload files on separate threads so the arm's movement is not blocked until upload is complete
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)

        # Generate positions where pictures will be taken
        steps = reversed(range(1000, 2200, 200))
        for step in steps:
            # Construct image path
            image_path = os.path.join(curr_sess_path, f"{step}.jpg")

            # Move arm to next position
            self.sc.execute_commands([(0, step)])

            # Wait a bit for stabilization
            sleep(0.5)

            # Take the picture
            self.camera.take_picture(image_path)

            # Upload it to S3
            executor.submit(self.storage.upload_file, "sorterbot", image_path)

    def move_object_to_container(self, obj_pos, cont_pos):
        self.sc.move_to_position(obj_pos)
        self.magnet.on()
        self.sc.move_to_position(cont_pos, is_container=True)
        self.magnet.off()

    def reset_arm(self):
        self.sc.execute_commands(((2, self.sc.start_positions[2]),))
        self.sc.execute_commands((
            (0, self.sc.start_positions[0]),
            (1, self.sc.start_positions[1]),
            (3, self.sc.start_positions[3])
        ), parallel=True)

    def close(self):
        if self.camera.camera.recording:
            self.camera.stop()
        self.reset_arm()
        self.sc.neutralize_servos()


commands = ArmCommands()

while True:
    try:
        cmd = int(input("Command: "))
        if cmd == 0:
            commands.close()
            break
        elif cmd == 1:
            commands.sc.init_arm_position()
        elif cmd == 2:
            commands.do_recording()
        elif cmd == 3:
            commands.take_pictures()
        elif cmd == 4:
            commands.sc.execute_command((commands.servos[3], 1780))
        elif cmd == 5:
            while True:
                servo = input("Servo: ")
                angle = input("Angle: ")
                commands.sc.execute_command((int(servo), int(angle),))
        elif cmd == 6:
            angle = input("Angle: ")
            dist = input("Distance: ")
            cont = bool(int(input("Is container: ")))
            commands.sc.move_to_position((int(angle), int(dist),), is_container=cont)
        elif cmd == 7:
            obj_angle = int(input("Object Angle: "))
            obj_dist = int(input("Object Distance: "))
            cont_angle = int(input("Container Angle: "))
            cont_dist = int(input("Container Distance: "))
            commands.move_object_to_container((obj_angle, obj_dist,), (cont_angle, cont_dist))
    except Exception as e:
        commands.close()
        raise e

    sleep(0.5)
