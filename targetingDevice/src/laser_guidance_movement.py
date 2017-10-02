"""Setting everything up for the Device"""
import os
import json
import time
import uuid
import logging
import argparse
import datetime
import threading
import pantilthat
from boto3.session import Session
from botocore.exceptions import ClientError
from random import choice
from string import lowercase


logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)



def move_guidance(xdelta, ydelta):
    log.info("Starting to move arm: {0}, {1}".format(xdelta, ydelta))
    pantilthat.pan(xdelta)
    pantilthat.tilt(ydelta)
    log.info("Finished moving arm: {0}, {1}".format(xdelta, ydelta))


