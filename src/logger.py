import logging
import logging.handlers

logger = logging.getLogger('SORTERBOT_RASPBERRY')

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

handler = logging.StreamHandler()
handler.setFormatter(formatter)
logger.addHandler(handler)

http_handler = logging.handlers.HTTPHandler('192.168.178.19:8000', '/log/', method='POST')
handler.setFormatter(formatter)
logger.addHandler(http_handler)

logger.setLevel(logging.DEBUG)
logger.setLevel(level=logging.DEBUG)
