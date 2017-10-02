"""Setting everything up for the Device"""
import os
import json
import time
import uuid
import logging
import argparse
import datetime
import threading
import ssl
import signal
from boto3.session import Session
from botocore.exceptions import ClientError
from random import choice
from string import lowercase
from laser_guidance_core import *
from laser_guidance_movement import move_guidance

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

policy_name_key = "lg_policy"
policy_arn_key = "lg_policy_arn"
thing_name_template = "lg_thing_{0}"
update_topic_name_template = "$aws/things/{0}/shadow/update/accepted"
get_topic_name_template = "$aws/things/{0}/shadow/get/accepted"

publish_get_topic_name_template = "$aws/things/{0}/shadow/get"
publish_update_topic_name_template = "$aws/things/{0}/shadow/update"
root_cert = os.getcwd() + '/' +'aws-iot-rootCA.crt'

AWS_IOT_MQTT_PORT = 8883

make_string = lambda x: "".join(choice(lowercase) for i in range(x))

class LaserGuidanceThing:

    keep_running = True

    x = 0
    y = 0

    def __init__(self,cli):
        self.thing_name = thing_name_template.format(cli.thing_number)
        thing_data = get_thing_data(self.thing_name)
        self.x = thing_data['x']
        self.y = thing_data['y']

    def signal_handler(self, signal, frame):
        print 'Caught signal, preparing to exit gracefully.'
        self.keep_running = False

    def _connect(self, cli, thing, cfg):
        region = cli.region
        aws_iot = get_iot_session(region, cli.profile_name)
        message_qos = 1

        # setup MQTT client
        lgid = uuid.UUID(cfg[lg_id_key])

        # use LG ID and a random string since we must use unique Client ID per
        # client.
        cid = lgid.urn.split(":")[2] + "_" + make_string(3)

        mqttc = AWSIoTMQTTClient(clientID=cid)

        endpoint = aws_iot.describe_endpoint()
        log.info("LaserGuidance connecting asynchronously to IoT endpoint:'{0}'".format(
            endpoint['endpointAddress']))
        mqttc.configureEndpoint(
            hostName=endpoint['endpointAddress'], portNumber=AWS_IOT_MQTT_PORT
        )
        mqttc.configureCredentials(
            CAFilePath=root_cert,
            KeyPath=cfg_dir + self.thing_name + ".prv",
            CertificatePath=cfg_dir + self.thing_name + ".pem"
        )
        mqttc.configureAutoReconnectBackoffTime(1, 128, 20)
        mqttc.configureOfflinePublishQueueing(90, DROP_OLDEST)
        mqttc.configureDrainingFrequency(3)
        mqttc.configureConnectDisconnectTimeout(20)
        mqttc.configureMQTTOperationTimeout(5)

        mqttc.connect() # keepalive default at 30 seconds

        return mqttc

    def subscribe(self, cli):
        """
        Subscribe
        """
        init(cli)

        cfg = get_lg_config()
        things = get_things_config()
        if not things:
            log.info("[subscribe] ELF couldn't find previously created things.")
            return

        t = things[cli.thing_number]
        thing = t[self.thing_name]

        self.mqttc = self._connect(cli, thing, cfg)

        update_topic = update_topic_name_template.format(self.thing_name)
        get_topic = get_topic_name_template.format(self.thing_name)
        log.info(
            "LG subscribing on topic root:'{0}'".format(update_topic))
        log.info(
            "LG subscribing on topic root:'{0}'".format(get_topic))

        self.mqttc.subscribe(update_topic, 1, self.listener_callback)
        self.mqttc.subscribe(get_topic, 1, self.listener_callback)
        log.info("LG {0} subscribed on topic: {1}, {2}".format(
            self.thing_name, update_topic, get_topic))

        time.sleep(1)

        publish_get_topic = publish_get_topic_name_template.format(self.thing_name)
        self.mqttc.publish(publish_get_topic, "", 1)

        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        while self.keep_running:
            time.sleep(5)

        thing_data = {
            "x": self.x,
            "y": self.y
        }
        update_thing_data(self.thing_name,thing_data)

        #start = datetime.datetime.now()
        #finish = start + datetime.timedelta(seconds=duration)
        #while finish > datetime.datetime.now():
        #    time.sleep(1) # wait a second between iterations


    def listener_callback(self, client, userdata, message):
        log.info("Received message: {0} from topic: {1}".format(
            message.payload, message.topic))
        shadow = json.loads(message.payload)
        if ("desired" in shadow["state"]):
            xdelta = shadow["state"]["desired"]["x"]-self.x
            ydelta = shadow["state"]["desired"]["y"]-self.y
            #move_guidance(xdelta,ydelta)
            move_guidance(shadow["state"]["desired"]["x"], shadow["state"]["desired"]["y"])
            self.x = self.x + xdelta
            self.y = self.y + ydelta
            publish_update_topic = publish_update_topic_name_template.format(self.thing_name)
            shadow = {
                'state': {
                    'reported': {
                        'x': self.x,
                        'y': self.y
                    }
                }

            }
            self.mqttc.publish(publish_update_topic, json.dumps(shadow), 0)


if __name__ == '__main__':
    print ssl.OPENSSL_VERSION

    parser = argparse.ArgumentParser(
        description='Simple way to generate IoT messages for multiple Things.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument('--region', dest='region', help='The AWS region to use.',
                        default='us-east-1')
    parser.add_argument('--profile', dest='profile_name',
                        help='The AWS CLI profile to use.')
    parser.add_argument('thing_number', nargs='?', default=0, type=int,
                      help="Thing to subscribe to.")

    args = parser.parse_args()

    lgt = LaserGuidanceThing(args)
    lgt.subscribe(args)
