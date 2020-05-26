import logging
import logging.handlers
from yaml import load, Loader, YAMLError


class Logger:
    def __init__(self, config_path):
        with open(config_path, 'r') as stream:
            try:
                config = load(stream, Loader)
            except YAMLError as error:
                print("Error while opening config.yaml ", error)

        self.logger = logging.getLogger('SORTERBOT_RASPBERRY')

        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

        http_handler = logging.handlers.HTTPHandler(f"{config['control_host']}:{config['control_port']}", '/log/', method='POST')
        handler.setFormatter(formatter)
        self.logger.addHandler(http_handler)

        self.logger.setLevel(logging.DEBUG)
        self.logger.setLevel(level=logging.DEBUG)
