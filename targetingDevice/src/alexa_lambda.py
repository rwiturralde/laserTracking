"""Sending movement commands to IoT"""
import logging
from LaserGuidanceIoTClient.movement import MovementClient


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event, context):
    """Lambda handler for sending command to IoT."""


    cmd = event["cmd"]
    delta = event["delta"]

    movement_client = MovementClient('lg_thing_0')

    if (cmd=="up"):
        movement_client.move_up(delta)

    if (cmd=="down"):
        movement_client.move_down(delta)

    if (cmd=="left"):
        movement_client.move_left(delta)

    if (cmd=="right"):
        movement_client.move_right(delta)

    return {"status": "command_sent"}

