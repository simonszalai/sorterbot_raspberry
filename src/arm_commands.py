"""
Contains the higher level commands that control the robotic arm. These commands are not directly controlling
the servo motors, they are doing higher level operations which consists of series of lower level steps.

"""


import os
import json
import asyncio
import requests
import websockets
import concurrent.futures
from datetime import datetime
from urllib.parse import urljoin
from pathlib import Path
from yaml import load, Loader, YAMLError

from camera import Camera
from storage import Storage
from magnet import MagnetControl
from servo_control import ServoControl
from logger import logger


class ArmCommands:
    def __init__(self):
        """
        Contains all the higher level commands used to control the robotic arm.

        """

        self.camera = Camera()
        self.storage = Storage()
        self.sc = ServoControl()
        self.magnet = MagnetControl()
        self.cloud_websocket = None

        self.current_set_path = self.storage.create_next_train_folder()

        # Parse config.yaml
        with open("arm_config.yaml", 'r') as stream:
            try:
                config = load(stream, Loader)
            except YAMLError as error:
                print("Error while opening config.yaml ", error)

        self.config = config
        self.cloud_url = f"http://{config['cloud_host']}:{config['cloud_port']}/"
        self.ws_cloud_url = f"ws://{config['cloud_host']}:{config['cloud_port']}"
        self.control_url = f"http://{config['control_host']}:{config['control_port']}/"

    def record_training_video(self):
        """
        Records a video which later can be used to create a training dataset by utilizing sorterbot_labeltool. After the video
        is recorded, it will be uploaded to the appropriate s3 bucket.

        """

        video_path = os.path.join(self.current_set_path, datetime.now().strftime("%d.%m.%Y_%H:%M:%S") + ".h264")
        self.camera.start(path=video_path)
        self.sc.execute_commands(((0, 800, "dataset"),))
        self.camera.stop()

        # Don't wait for upload to finish before initializing the arm
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        executor.submit(self.storage.upload_file, "sorterbot-training-videos", video_path)
        executor.submit(self.sc.init_arm_position)

    async def infer_and_sort(self):
        """
        Controls the process of localizing objects and moving them to the containers on the Raspberry side.
        First it takes images for inference, sends them for processing, and after all of them were successfully processed,
        requests the session's commands from the cloud service. After the commands are received, executes them one by one
        and returns the arm to the initial position.

        """

        # Construct session path
        self.curr_sess_path = self.storage.create_next_session_folder()

        # Generate positions where pictures will be taken
        steps = list(reversed(range(1000, 2000, 50)))

        # Create new session at the Control Panel
        self.arm_id = self.config["arm_id"]
        self.session_id = os.path.basename(self.curr_sess_path)
        requests.post(self.control_url + "api/sessions/", json={
            "arm": self.arm_id,
            "session_id": self.session_id,
            "status": "In Progress",
            "log_filenames": ",".join(reversed([str(step) for step in steps]))
        })

        # Take pictures and send them for processing
        all_success = await self.take_pictures(steps)

        log_args = {"arm_id": self.arm_id, "session_id": self.session_id, "log_type": "comm_exec"}

        # If all successful, send a request to process session images and generate commands
        if all_success:
            logger.info("All images successfully processed, requesting commands...", dict(bm_id=8, **log_args))
            async with websockets.connect(self.ws_cloud_url) as cloud_websocket:
                await cloud_websocket.send(json.dumps({
                    "command": "get_commands_of_session",
                    "session_id": Path(self.curr_sess_path).name,
                    "arm_constants": self.config
                }))
                commands_as_pw = json.loads(await cloud_websocket.recv())
                logger.info("Commands received.", dict(bm_id=17, **log_args))
            if len(commands_as_pw) == 0:
                logger.warning("No containers were found, moving to initial position.", log_args)
        else:
            commands_as_pw = []
            logger.error("At least one image failed processing, moving to initial position.", log_args)

        # Instruct arm to move each object to the appropriate containers
        for cmd in commands_as_pw:
            self.sc.move_to_position(cmd[0])
            logger.info(f"Arm moved to object at position ({int(cmd[0][0])}, {int(cmd[0][1])}) for pick up.", log_args)
            self.magnet.on()
            logger.info(f"Magnet ON.", log_args)
            self.sc.move_to_position(cmd[1], is_container=True)
            logger.info(f"Arm moved to container at position ({int(cmd[1][0])}, {int(cmd[1][1])}) for drop off.", log_args)
            self.magnet.off()
            logger.info(f"Magnet OFF.", log_args)

        logger.info("Commands executed.", dict(bm_id=18, **log_args))

        # Take pictures and send them for after picture
        all_success = await self.take_pictures(steps, is_after=True)

        logger.info("All after pictures taken and uploads started.", dict(bm_id=15, **log_args))

        # Start stitching of after image
        async with websockets.connect(self.ws_cloud_url) as cloud_websocket:
            await cloud_websocket.send(json.dumps({
                "command": "stitch_after_image",
                "arm_id": self.config["arm_id"],
                "session_id": Path(self.curr_sess_path).name
            }))

        logger.info("Stitching after images started.", dict(bm_id=16, **log_args))

        # Reset arm to initial position
        self.reset_arm()
        logger.info(f"Arm reset to initial position, session finished.", dict(session_finished=1, bm_id=25, **log_args))

    async def take_pictures(self, steps, is_after=False):
        """
        Takes pictures for inference. After the pictures are taken, they will be sent over WebSockets to
        Cloud service to start inference and locate objects of interest. This function will wait for all the images
        to be processed, and finally it will check if all of them were successfully processed.

        Parameters
        ----------
        steps : list of ints
            List containing pulse widths of servo 0 where images should be taken.

        Returns
        -------
        all_success : bool
            Boolean indicating if all the images were successfully processed.
        is_after : bool
            Boolean representing is the current image recording session is for creating an overview stitched image after the objects have
            been moved to the containers.

        """

        # Init arm position for inference
        self.sc.init_arm_position(is_inference=True)

        # Execute sequence
        tasks = []
        for step in steps:
            log_args = {"arm_id": self.arm_id, "session_id": self.session_id, "log_type": step}

            # Construct image path
            image_path = Path(self.curr_sess_path).joinpath(f"{step}.jpg")

            # Move arm to next position
            self.sc.execute_commands([(0, step)])
            logger.info(f"Arm is in position for picture '{step}'.", log_args)

            # Wait a bit for stabilization (and upload previous results in the meantime)
            await asyncio.sleep(0.5)
            logger.info(f"Arm is stabilized.", log_args)

            # Take the picture
            self.camera.take_picture(image_path.as_posix())
            logger.info(f"Picture '{step}' taken.", dict(bm_id=1, **log_args))

            # Send picture directly to Cloud service
            task = asyncio.create_task(self.send_image_for_processing(image_path, step, is_after))
            tasks.append(task)

        results = []
        for task in asyncio.as_completed(tasks):
            success, step = await task
            print("step", step)
            results.append({
                "image_id": step,
                "success": success
            })

        logger.info("All images successfully processed.", {"arm_id": self.arm_id, "session_id": self.session_id, "log_type": "comm_gen"})

        # Check if all of the pictures were processed successfully
        all_success = all([res["success"] for res in results])

        if not all_success:
            failed_images = [res["image_id"] for res in results if not res["success"]]
            logger.error(f"Processing failed for the following images: {failed_images}", log_args)

        return all_success

    async def send_image_for_processing(self, image_path, step, is_after):
        """
        Takes an image from disk, opens it and send the image bytes directly to the Cloud service. It creates a new connection for each
        image, where the image metadata is sent as headers of the initial HTTP handshake.

        Parameters
        ----------
        image_path : str
            Path of the image on disk to be uploaded and processed.
        step : int
            Identifies the image, corresponds to the pulse width of servo 0 where the image was taken. Used to correctly
            place the log after upload was done.
        is_after : bool
            Boolean representing is the current image recording session is for creating an overview stitched image after the objects have
            been moved to the containers.

        Returns
        -------
        success : bool
            Boolean representing if image processing was successful.
        step : int
            Identifies the image, corresponds to the pulse width of servo 0 where the image was taken. Used to correctly
            place the log after upload was done. It is passed through the function and used to report the execution results.

        """

        log_args = {"arm_id": self.arm_id, "session_id": self.session_id, "log_type": step}

        # Read image bytes
        with open(image_path, "rb") as img_file:
            img_bytes = img_file.read()

        # Construct headers for initial HTTP handshake
        headers = websockets.http.Headers({
            "command": "recv_img_after" if is_after else "recv_img_proc",
            "arm_id": self.arm_id,
            "session_id": self.session_id,
            "image_name": Path(image_path).name
        })

        # Send image bytes
        async with websockets.connect(self.ws_cloud_url, extra_headers=headers) as cloud_websocket:
            await cloud_websocket.send(img_bytes)
            logger.info(f"Image {Path(image_path).name} successfully sent to Cloud service.", log_args)
            success = await cloud_websocket.recv()

            # Delete file locally if successfully processed
            if success:
                logger.info(f"Image {Path(image_path).name} successfully processed.", log_args)
                os.remove(image_path)

            return success, step

    def reset_arm(self):
        """
        Instructs the arm to return to the start position.

        """

        self.sc.execute_commands(((2, self.sc.start_positions[2]),))
        self.sc.execute_commands((
            (0, self.sc.start_positions[0]),
            (1, self.sc.start_positions[1]),
            (3, self.sc.start_positions[3])
        ), parallel=True)
        self.sc.neutralize_servos()

    def close(self):
        """
        Closes the session: stops the camera in case it's recording, moves the arm to starting position and neutralizes the servos.

        """

        if self.camera.camera.recording:
            self.camera.stop()
        self.reset_arm()
        self.sc.neutralize_servos()


# commands = ArmCommands()

# while True:
#     try:
#         cmd = int(input("Command: "))
#         if cmd == 0:
#             commands.close()
#             break
#         elif cmd == 1:
#             commands.sc.init_arm_position()
#         elif cmd == 2:
#             commands.record_training_video()
#         elif cmd == 3:
#             commands.take_pictures()
#         elif cmd == 4:
#             commands.sc.execute_command((commands.servos[3], 1780))
#         elif cmd == 5:
#             while True:
#                 servo = input("Servo: ")
#                 angle = input("Angle: ")
#                 commands.sc.execute_command((int(servo), int(angle),))
#         elif cmd == 6:
#             angle = input("Angle: ")
#             dist = input("Distance: ")
#             cont = bool(int(input("Is container: ")))
#             commands.sc.move_to_position((int(angle), int(dist),), is_container=cont)
#         elif cmd == 7:
#             obj_angle = int(input("Object Angle: "))
#             obj_dist = int(input("Object Distance: "))
#             cont_angle = int(input("Container Angle: "))
#             cont_dist = int(input("Container Distance: "))
#             commands.move_object_to_container((obj_angle, obj_dist,), (cont_angle, cont_dist))
#         elif cmd == 8:
#             pixel_angle = int(input("Pixel angle: "))
#             new_pw_angle = commands.convert_command_angle(pixel_angle)
#             print(new_pw_angle)
#         elif cmd == 9:
#             commands.infer_and_sort()
#         elif cmd == 10:
#             commands.convert_command_to_polar({
#                 "img_base_angle": 1425,
#                 "img_dims": [1640, 1232],
#                 "locations_as_pixels": ((820, 0,), (820, 1232,),)
#             })
#         elif cmd == 11:
#             commands.filter_duplicate_positions([(1455.8194454670409, 1640.2550963180688), (1305.3293199180484, 1232.5792585756476), (1020.130933314334, 1844.6160327887617), (1339.5320714079303, 1855.2308768926205), (1561.6438853079546, 1307.4115533251302), (1740.7008299435813, 1523.2044400191508), (1619.2404831864485, 1339.1886733551323), (1700.0540257146777, 1507.7658838736122), (1467.7368179032735, 1647.7691177720542), (1314.814153218803, 1234.5349345090485), (1350.7423864318368, 1864.9636021690299), (1575.215952456132, 1304.2532593094427), (1656.1526068281983, 1727.5550014215837), (1015.4801892454399, 1822.9144826194706), (1292.6923350135394, 1247.4895924617376), (1300.9698980485962, 1456.495902509347), (1724.5350831335736, 1514.0857223938847), (1684.8220078074987, 1749.2826567152358), (1597.6762654563888, 1318.4475549061426), (1709.7546353079906, 1511.1570045990097), (1487.1105754946368, 1654.7772611680075), (1672.505961718362, 1737.8291536149027), (1366.4454348457552, 1883.4748152407078), (1589.4983507666955, 1312.7055035675012), (1326.3400103385557, 1249.2387899050423)])
#     except Exception as e:
#         commands.close()
#         raise e

#     sleep(0.5)
