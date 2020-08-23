# SorterBot Raspberry
Medium articles about the project: [Part 1](https://medium.com/swlh/web-application-to-control-a-swarm-of-raspberry-pis-with-an-ai-enabled-inference-engine-b3cb4b4c9fd), [Part 2](https://medium.com/@simon.szalai/web-application-to-control-a-swarm-of-raspberry-pis-with-an-ai-enabled-inference-engine-part-2-73804121c98a), [Part 3](https://medium.com/@simon.szalai/web-application-to-control-a-swarm-of-raspberry-pis-with-an-ai-enabled-inference-engine-part-3-77836f9fc4c2)

Part of the SorterBot project, which should be installed in any Raspberry Pi connected to the service. Once started, this script will poll the Control Panel in regular intervals, report the Pi's status, and check if a new session was initiated by the user. In case a new session is started and the Cloud Service is online, it will take a series of pictures, send them to the Cloud Service, wait for the commands, and execute them as they arrive, by moving the recognized objects to their appropriate containers with the help of the magnet installed on the robotic arm.
<p align="center"><img src="./media/arm.gif"/></p>
<p align="center" font-style="italic">Figure 1: The Robotic Arm in action</p>

### Configure the arm
Make a copy of the file `arm_config.yaml.example`, and change the values according to the documentation below.

Details coming soon.
