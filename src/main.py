import json
import requests
from time import sleep
from urllib.parse import urljoin
from yaml import load, dump, Loader, YAMLError

from arm_commands import ArmCommands

commands = ArmCommands()


def one_checkin_cycle():
    # Parse config.yaml
    with open("arm_config.yaml", 'r') as stream:
        try:
            config = load(stream, Loader)
        except YAMLError as error:
            print("Error while opening config.yaml ", error)

    # Get Cloud Service Public IP from Control Panel
    response_1 = requests.post(urljoin(config["control_url"], "get_cloud_ip") + "/", json={"arm_id": config["arm_id"]})
    cloud_ip = "192.168.178.19"  # str(json.loads(response_1.content)["cloud_ip"])

    # Save newly retrieved Cloud IP to config
    config["cloud_ip"] = cloud_ip
    with open("arm_config.yaml", "w") as outfile:
        dump(config, outfile, default_flow_style=False)

    # Try to connect to Cloud Service using the IP retrieved above
    try:
        cloud_url = f"http://{config['cloud_ip']}:{config['cloud_port']}/"
        response_2 = requests.get(urljoin(cloud_url, "arm_checkin"))
        cloud_connect_success = json.loads(response_2.content)["arm_checkin"]
        print("Connection to SorterBot Cloud is successful.")
    except requests.exceptions.RequestException:
        print("SorterBot Cloud is down.")
        cloud_connect_success = 0

    # Report back to Control Panel if connecting to the Cloud Service was successful
    payload = {
        "arm_id": config["arm_id"],
        "cloud_connect_success": cloud_connect_success
    }
    response_3 = requests.post(urljoin(config["control_url"], "send_connection_status") + "/", json=payload)
    print(response_3)
    print(json.loads(response_3.content))
    should_start_session = json.loads(response_3.content)["should_start_session"]

    return should_start_session


while True:
    print("Checking in...")
    should_start_session = one_checkin_cycle()
    if should_start_session:
        # commands.infer_and_sort()
        sleep(3)
    else:
        sleep(3)
