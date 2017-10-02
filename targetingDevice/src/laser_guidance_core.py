"""Setting everything up for the Device"""
import os
import json
import time
import uuid
import logging
import argparse
import datetime
import threading
from boto3.session import Session
from botocore.exceptions import ClientError
from random import choice
from string import lowercase

from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient, DROP_OLDEST

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

lg_id_key = "lg_id"
lg_id = None
lg_cfg_dir = "misc"
full_certs = "things.json"
cfg_dir = os.getcwd() + '/' + lg_cfg_dir + '/'
lg_file_dir = "misc"
lg_file = "lg.json"


def update_thing_data(thing_name, thing_data):
    things_file = cfg_dir + thing_name+".json"
    with open(things_file, "w") as fc_file:
        json.dump(thing_data, fc_file, indent=2,
                  separators=(',', ': '), sort_keys=True)
        log.info("Wrote {0} thing_data to data file: {1}".format(
            json.dumps(thing_data), things_file))


def get_thing_data(thing_name):
    thing_data = {
        "x": 0,
        "y": 0
    }
    things_file = cfg_dir + thing_name+".json"
    if os.path.exists(things_file) and os.path.isfile(things_file):
        try:
            with open(things_file, "r") as in_file:
                thing_data = json.load(in_file)
        except OSError as ose:
            log.error('OSError while reading LG thing config file. {0}'.format(
                ose))
    return thing_data


def update_things_config(things):
    things_file = cfg_dir + full_certs
    with open(things_file, "w") as fc_file:
        json.dump(things, fc_file, indent=2,
                  separators=(',', ': '), sort_keys=True)
        log.info("Wrote {0} things to config file: {1}".format(
            len(things), things_file))


def get_things_config():
    things = None
    things_file = cfg_dir + full_certs
    if os.path.exists(things_file) and os.path.isfile(things_file):
        try:
            with open(things_file, "r") as in_file:
                things = json.load(in_file)
        except OSError as ose:
            log.error('OSError while reading LG thing config file. {0}'.format(
                ose))
    return things


def update_lg_config(cfg):
    dirname = os.getcwd() + '/' + lg_file_dir
    log.debug(
        '[update_lg_config] checking for directory:{0}'.format(dirname))
    if not os.path.exists(dirname):
        try:
            os.makedirs(dirname)
        except OSError as ose:
            log.error("Error creating directory:{0} {1}".format(dirname, ose))
            log.error("Tring to create directory: {0} again".format(dirname))
            os.makedirs(dirname)

    filename = os.getcwd() + '/' + lg_file_dir + '/' + lg_file
    try:
        with open(filename, "w") as out_file:
            json.dump(cfg, out_file)
            log.debug("Wrote LaserGuidance config to file: {0}".format(cfg))
    except OSError as ose:
        log.error('OSError while writing LaserGuidance config file. {0}'.format(ose))


def get_lg_config():
    lg = None
    filename = os.getcwd() + '/' + lg_file_dir + '/' + lg_file
    if os.path.exists(filename) and os.path.isfile(filename):
        try:
            with open(filename, "r") as in_file:
                lg = json.load(in_file)
        except OSError as ose:
            log.error('OSError while reading LaserGuidance config file. {0}'.format(ose))
    return lg


def init(cli):
    # Initialize local configuration file and LaserGuidance's unique ID
    global lg_id
    lg = get_lg_config()
    if lg:
        lg_id = uuid.UUID(lg[lg_id_key])
        log.info("Read LaserGuidance ID from config: {0}".format(lg_id))
    else:  # file does not exist, so create our ELF ID
        lg_id = uuid.uuid4()
        out_item = {lg_id_key: lg_id.urn}
        update_lg_config(out_item)
        log.info("Wrote LaserGuidance ID to config: {0}".format(out_item[lg_id_key]))

def get_iot_session(region, profile_name):
    if profile_name is None:
        log.debug("LaserGuidance loading AWS IoT client using 'default' AWS CLI profile")
        return Session(region_name=region).client('iot')

    log.debug("LaserGuidance loading AWS IoT client using '{0}' AWS CLI profile".format(
        profile_name))
    return Session(
        region_name=region,
        profile_name=profile_name).client('iot')

