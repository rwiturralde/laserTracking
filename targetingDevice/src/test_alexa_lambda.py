"""Call register function."""
import requests
import json
import logging

from alexa_lambda import *


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

lambda_handler({"cmd": "up", "delta": 5},{})

lambda_handler({"cmd": "down", "delta": 5},{})

lambda_handler({"cmd": "left", "delta": 5},{})

lambda_handler({"cmd": "right", "delta": 5},{})

