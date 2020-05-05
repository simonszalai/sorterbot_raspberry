# import ssl
import json
import asyncio
import websockets
# from pathlib import Path
from time import sleep
from yaml import load, dump, Loader, YAMLError

from arm_commands import ArmCommands


class Main:
    """
    Manages WebSocket connections to Cloud service and Control Panel and starts new sessions as instructions from the user arrives
    from the Control Panel. The connections are opened when this file is run and periodically checked with pings if they are still working.
    If a connection is not responding, it is automatically closed and reopened. If the WebSocket server is down, the client will try to
    reconnect periodically. At the end of every heartbeat, connection status is reported to the Control Panel.

    Parameters
    ----------
    heart_rate : int
        Length of interval in seconds in which the connection checks and status reports are executed.

    """

    def __init__(self, heart_rate=3):
        self.heart_rate = heart_rate
        self.load_config()
        self.loop = asyncio.get_event_loop()
        self.control_websocket = None
        self.cloud_websocket = None
        self.commands = ArmCommands()

        # self.ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        # localhost_pem = Path(__file__).parent.parent.joinpath("cert.pem")
        # self.ssl_context.load_verify_locations(localhost_pem)

    async def heartbeat(self):
        """
        Heartbeat function, which is executed in a certain interval to check WebSocket connection statuses and set up
        connections as needed. First, it checks if there is an open and responsive connection to the Cloud service. If not, it will
        try to open a connection using the host address saved in arm_config.yaml. If the connection cannot be opened, retrieves the
        Cloud host address from the Control Panel and tries to establish a connection using that. If it succeeds, the new host will
        be saved to arm_config.yaml. Finally, the connection status is sent to the Control Panel. In case there is a healthy connection
        to the Cloud service and the user pressed the start button, a new session will be initiated. If there is no connection, the
        session will not be started even if the start button was pressed.

        Returns
        -------
        should_start_session : int
            0 or 1, representing if the session should be started. Integer values are used instead of bool, because they are directly
            JSON serializable. If there is no connection to the Cloud service, the session cannot be started.

        """

        cloud_conn_status = 0

        if self.cloud_websocket and self.cloud_websocket.open:
            # If Cloud connection is open, try to ping it
            cloud_conn_status = await self.ping_cloud()
        else:
            # If Cloud connection is closed, open it
            success_connecting = await self.connect_cloud()
            if not success_connecting:
                # If openin connection was not successful, retreive the latest host address from Control Panel and try to connect with that
                cloud_conn_status = await self.get_cloud_host_and_connect()

        # Report back to Control Panel if connecting to the Cloud Service was successful and see if a new session should be started
        await self.control_websocket.send(json.dumps({
            "command": "send_conn_status",
            "arm_id": self.config["arm_id"],
            "cloud_conn_status": cloud_conn_status
        }))
        should_start_session = json.loads(await self.control_websocket.recv())

        return should_start_session

    async def connect_control(self):
        """
        Opens a WebSockets connection to the Control Panel using the address saved in arm_config.yaml. If the connection fails, it will keep
        trying until it succeeds.

        """

        control_url = f"ws://{self.config['control_host']}:{self.config['control_port']}/rpi/"
        control_connected = False
        while not control_connected:
            try:
                self.control_websocket = await websockets.connect(control_url)
                pong_waiter = await self.control_websocket.ping()
                await pong_waiter
                control_connected = True
                print("Control Panel is online.")
            except (ConnectionRefusedError, websockets.exceptions.ConnectionClosedError, websockets.exceptions.InvalidMessage):
                print("Control Panel is offline. Retrying in 3s...")
                sleep(self.heart_rate)

    async def connect_cloud(self, cloud_host=None):
        """
        Opens a WebSockets connection to the Cloud service.

        Parameters
        ----------
        cloud_host : str
            Optional parameter to specify the host of the connection. If none is provided, the host saved to the config file will be used.

        Returns
        -------
        connection_success : int
            0 or 1, representing if connecting to the Cloud service succeeded. Integer values are used
            instead of bool, because they are directly JSON serializable.

        """

        self.cloud_url = f"ws://{cloud_host or self.config['cloud_host']}:{self.config['cloud_port']}"
        try:
            self.cloud_websocket = await websockets.connect(self.cloud_url)
            pong_waiter = await self.cloud_websocket.ping()
            await pong_waiter
            return 1
        except (ConnectionRefusedError, websockets.exceptions.ConnectionClosedError, websockets.exceptions.InvalidMessage):
            if cloud_host:
                print("Cloud service is offline with latest host as well.")
            else:
                print("Cloud service is offline.")
            return 0

    async def ping_cloud(self):
        """
        Pings to WebSockets connection to the Cloud service. If the ping fails, closes the connection.

        Returns
        -------
        connection_success : int
            0 or 1, representing if pinging the Cloud service succeeded. Integer values are used
            instead of bool, because they are directly JSON serializable.

        """

        try:
            pong_waiter = await self.cloud_websocket.ping()
            await pong_waiter
            print("SorterBot Cloud is online.")
            return 1
        except (ConnectionRefusedError, websockets.exceptions.ConnectionClosedError, websockets.exceptions.InvalidMessage):
            print("WebSocket connection to SorterBot Cloud exists, but it is unresponsive, closing connection.")
            await self.cloud_websocket.close()
            self.cloud_websocket = None
            return 0

    async def get_cloud_host_and_connect(self):
        """
        Retrieves the latest address of the Cloud service from the Control Panel and attempts to connect using the
        new host. If the connection succeeds, saves the new host to the config file.

        Returns
        -------
        connection_success : int
            0 or 1, representing if the attempted connection using the new host succeeded. Integer values are used
            instead of bool, because they are directly JSON serializable.

        """

        # Retrieve Cloud host from Control Panel
        await self.control_websocket.send(json.dumps({
            "command": "get_cloud_ip",
            "arm_id": self.config["arm_id"]
        }))
        new_cloud_host = json.loads(await self.control_websocket.recv())

        # Try to connect to Cloud service with the new host
        connected_to_new_host = await self.connect_cloud(cloud_host=new_cloud_host)

        if connected_to_new_host:
            # if connection was successful, save new host to config
            self.config["cloud_host"] = new_cloud_host
            with open("arm_config.yaml", "w") as outfile:
                dump(self.config, outfile, default_flow_style=False)
            # Reload config file to memory here, as this is the only place where it can be changed programmatically
            self.load_config()
            return 1
        else:
            return 0

    def load_config(self):
        """
        Loads the contents of the config file (arm_config.yaml)

        """

        with open("arm_config.yaml", 'r') as stream:
            try:
                self.config = load(stream, Loader)
            except YAMLError as error:
                print("Error while opening config.yaml ", error)


if __name__ == "__main__":
    main = Main()
    try:
        while True:
            # Open connection to Control Panel if it's not open
            if not main.control_websocket or not main.control_websocket.open:
                print("Control Panel is offline, connecting...")
                main.loop.run_until_complete(main.connect_control())

            print("Checking in...")
            should_start_session = main.loop.run_until_complete(main.heartbeat())
            print(f"session should start: {should_start_session}")
            # should_start_session = True
            if should_start_session:
                if main.cloud_websocket:
                    main.loop.run_until_complete(main.commands.infer_and_sort())
                else:
                    raise Exception("WebSocket connection is closed!")
                sleep(main.heart_rate)
            else:
                sleep(main.heart_rate)
    except KeyboardInterrupt:
        main.loop.run_until_complete(main.control_websocket.close())
        main.loop.run_until_complete(main.cloud_websocket.close())
        print("WebSocket connections to Cloud service and Control Panel closed.")
