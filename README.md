# SorterBot Raspberry
*Note: This repository is still work in progress!*

Part of the SorterBot project, which should be installed in any Raspberry Pi connected to the service. Once started, this script will poll the Control Panel in regular intervals, report the Pi's status, and check if a new session was initiated by the user. In case a new session is started and the Cloud Service is online, it will take a series of pictures, send them to the Cloud Service, wait for the commands, and execute them as they arrive, by moving the recognized objects to their appropriate containers with the help of the magnet installed on the robotic arm.

![Alt SorterBot Robotic Arm](./media/arm.gif)
*<p align="center">Figure 1: The Roboitc Arm in action</p>*

### Configure the arm
Make a copy of the file `arm_config.yaml.example`, and change the values according to the documentation below.

Details coming soon.
