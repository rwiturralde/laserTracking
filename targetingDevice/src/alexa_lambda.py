import json
import boto3
import logging
import traceback
import os
from botocore.exceptions import ClientError

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.INFO)

class MovementClient:

    thing_name = None

    def __init__(self, thing_name):
        self.thing_name = thing_name
        self.client = boto3.client('iot-data')


    def _get_shadow(self):
        response = self.client.get_thing_shadow(
            thingName=self.thing_name
        )
        shadow = json.loads(response['payload'].read())
        return shadow

    def _get_current_coordinates(self):
        try:
            shadow = self._get_shadow()
            x=0
            y=0
            # First pull the reported state
            if ('reported' in shadow['state']):
                if ('x' in shadow['state']['reported']):
                    x=shadow['state']['reported']['x']
                if ('y' in shadow['state']['reported']):
                    y=shadow['state']['reported']['y']
            # Desired state should override reported to avoid repeated asks
            if ('desired' in shadow['state']):
                if ('x' in shadow['state']['desired']):
                    x=shadow['state']['desired']['x']
                if ('y' in shadow['state']['desired']):
                    y=shadow['state']['desired']['y']
            return x,y
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                return 0,0
            raise RuntimeError("Unexpected error with boto: " + traceback.format_exc())


    def _update_desired(self,x,y):
        shadow = {
            'state': {
                'desired': {
                    'x': x,
                    'y': y
                }
            }

        }
        response = self.client.update_thing_shadow(
            thingName=self.thing_name,
            payload=json.dumps(shadow)
        )


    def move_up(self, ydelta):
        x,y = self._get_current_coordinates()
        y=y-ydelta
        self._update_desired(x,y)

    def move_down(self, ydelta):
        x,y = self._get_current_coordinates()
        y=y+ydelta
        self._update_desired(x,y)

    def move_left(self, xdelta):
        x,y = self._get_current_coordinates()
        x=x+xdelta
        self._update_desired(x,y)

    def move_right(self, xdelta):
        x,y = self._get_current_coordinates()
        x=x-xdelta
        self._update_desired(x,y)

def handler(event, context):
    try:
        """Lambda handler for sending command to IoT."""
        log.info('Handling event: %s' % event)
        cmd = None
        delta = int(os.environ['default_step_amount']) if 'default_step_amount' in os.environ else 10
        
        if 'currentIntent' in event and 'slots' in event['currentIntent']:
            slots = event['currentIntent']['slots']
            if 'Direction' in slots and not slots['Direction'] is None:
                cmd = slots['Direction']
            if 'Amount' in slots and not slots['Amount'] is None:
                delta = slots['Amount']
    
        movement_client = MovementClient('lg_thing_0')
    
        if (cmd=="up"):
            log.info('Moving up %s' % delta)
            movement_client.move_up(delta)
        elif (cmd=="down"):
            log.info('Moving down %s' % delta)
            movement_client.move_down(delta)
        elif (cmd=="left"):
            log.info('Moving left %s' % delta)
            movement_client.move_left(delta)
        elif (cmd=="right"):
            log.info('Moving right %s' % delta)
            movement_client.move_right(delta)
        else:
            log.warning('Unrecognized direction. Resetting laser to origin.')
            movement_client._update_desired(0,0)
        
        return {
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': 'Fulfilled',
            "message": {
                'contentType': 'PlainText',
                'content': "Message sent to IoT"
                }
            }
        }
    except:
        log.error("Unexpected error: %s" % traceback.format_exc())
        return {
        'dialogAction': {
            'type': 'Close',
            'fulfillmentState': 'Failed',
            "message": {
                'contentType': 'PlainText',
                'content': traceback.format_exc()
                }
            }
        }
