#! /usr/bin/env python
import argparse
import os, boto3
from contextlib import closing
import cv2
import sys
import numpy as np
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import json
import RPi.GPIO as gpio
import random
import threading

'''
Uses a camera to track a laser pointer and instruct it, via dictation,
to move toward a destination.
'''
class LaserTracker(object):

    def __init__(self):
        self.gpio_pins = [18, 23, 24]
        # How often we'll dictate commands
        self.command_interval = 1.5 #seconds
        self.hit_radius_px = 70 # pixels
        self.defaultRegion = 'us-east-1'
        self.defaultPollyEndpoint = 'https://polly.us-east-1.amazonaws.com'
        gpio.setmode(gpio.BCM)
        gpio.setwarnings(False)
        
        for pin in self.gpio_pins:
            gpio.setup(pin, gpio.OUT)
        
        return

    '''
    Create a boto3 AWS Polly client
    '''
    def connectToPolly(self, regionName=None, endpointUrl=None):
        regionName = regionName if regionName is not None else self.defaultRegion
        endpointUrl = endpointUrl if endpointUrl is not None else self.defaultPollyEndpoint
        print("Connecting to Polly in " + regionName + " at URL " + endpointUrl)
        return boto3.client('polly', region_name=regionName, endpoint_url=endpointUrl)
    
    '''
    Create a boto3 AWS Lex client
    '''
    def connectToLex(self, regionName=None):
        regionName = regionName if regionName is not None else self.defaultRegion
        print("Connecting to LEX in " + regionName)
        return boto3.client('lex-runtime', region_name=regionName)

    '''
    Use a given AWS Polly boto3 client to dictate a string of text.
    Can optionally specify the file format for the audio and the dictation voice
    '''
    def speak(self, polly, text, format='ogg_vorbis', voice='Joanna'):
        now = time.time()
        #filename = 'tmp.ogg'
        filename = text.replace(' ', '_') + '.ogg'
        # look for cached result
        if os.path.isfile(filename):
            print("Previous audio file found. Playing: " + filename)
            os.system('omxplayer ' + filename)
        else:
            # No cached result, so fetch from Polly
            print("No previous result for audio filename: " + filename + ". Calling Polly...")
            resp = polly.synthesize_speech(OutputFormat=format, Text=text, VoiceId=voice)
            with closing(resp["AudioStream"]) as stream:
                # mp3 files were playing the with end clipped via omxplayer.
                soundfile = open(filename, 'wb')
                soundfile.write(stream.read())
                soundfile.flush()
                soundfile.close()
                os.system('omxplayer ' + filename + ' > /dev/null')

        print("Spoke audio in " + str(time.time() - now) + " seconds")

    '''
    '''
    def send_to_lex(self, polly_client, lex_client, text='Hello world', botName='testing', botAlias='test_alias', userId='targetingDefault', voice='Joanna', \
                          lexContentType='audio/x-l16; sample-rate=16000; channel-count=1'):
        
        lex_parsed = False
        
        while not lex_parsed:
            start = time.time()
            print("Calling Polly for command " + text)
            resp = polly_client.synthesize_speech(OutputFormat='pcm', SampleRate='16000', Text=text, VoiceId=voice)
            print("Sending Polly response to Lex for command " + text)
            with closing(resp["AudioStream"]) as stream:
                lex_resp = lex_client.post_content(botName=botName, botAlias=botAlias, userId=userId, contentType=lexContentType, inputStream=stream.read())
                print("Fetched audio and posted to Lex in " + str(time.time() - start) + " seconds")
                
                if lex_resp['dialogState'] == 'ElicitIntent':
                    print('Lex failed to parse command: ' + text + '. Retrying... \nResponse: ' + lex_resp)
                else:
                    lex_parsed = True


    def detect(self, frame):
        # Blur to smooth edges of shapes
        blurred = cv2.GaussianBlur(frame, (11,11), 0)
        #hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_blurred = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        # define the lower and upper boundaries
        # in the HSV color space
        lower_red = np.array([166, 31, 122])
        upper_red = np.array([250, 250, 255])
        lower_green = np.array([40, 15, 140])
        upper_green = np.array([72, 255, 255])
        
        # construct a mask for the colors, then perform
        # a series of dilations and erosions to remove any small
        # blobs left in the mask
        red_mask = cv2.inRange(hsv_blurred, lower_red, upper_red)
        red_mask = cv2.erode(red_mask, None, iterations=2)
        red_mask = cv2.dilate(red_mask, None, iterations=2)
        green_mask = cv2.inRange(hsv_blurred, lower_green, upper_green)
        green_mask = cv2.erode(green_mask, None, iterations=2)
        green_mask = cv2.dilate(green_mask, None, iterations=2)

        # find contours in the mask and initialize the current
        # (x, y) center of the ball
        green_cnts = cv2.findContours(green_mask.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)[-2]
        red_cnts = cv2.findContours(red_mask.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)[-2]
        green_center = None
        red_center = None

        if len(green_cnts) > 0:
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(green_cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            if "m00" in M and M["m00"] > 0:
                green_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            else:
                green_center = (x,y)
            
            # only proceed if the radius meets a minimum size
            if radius > 10:
                # draw the circle and centroid on the frame,
                cv2.circle(frame, (int(x), int(y)), int(radius),
                        (0, 255, 255), 2)
                cv2.circle(frame, green_center, 5, (0, 0, 255), -1)
        
        if len(red_cnts) > 0:
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(red_cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            if "m00" in M and M["m00"] > 0:
                red_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            else:
                red_center = (x,y)

            # only proceed if the radius meets a minimum size
            if radius > 10:
                # draw the circle and centroid on the frame,
                cv2.circle(frame, (int(x), int(y)), int(radius),
                        (0, 255, 255), 2)
                cv2.circle(frame, red_center, 5, (0, 0, 255), -1)

        cv2.imshow('frame',frame)
        
        diff = None
        if green_center is not None and red_center is not None:
            diff = np.subtract(red_center, green_center)
        
        return diff

    def run(self):
        #initialize polly connection
        polly = self.connectToPolly()
        lex = self.connectToLex()
        
        #turn on a random target light
        self.lit_gpio_pin = random.choice(self.gpio_pins)
        gpio.output(self.lit_gpio_pin, gpio.HIGH)
        
        # initialize the camera and grab a reference to the raw camera capture
        # with-block ensures camera.close() is called upon exit.
        #with PiCamera(resolution = (640, 480),framerate = 15) as camera:
        with PiCamera(resolution = (1280, 960),framerate = 15) as camera:
            try:
                #camera.hflip = True
                #camera.vflip = True

                # allow the camera to warmup
                time.sleep(0.1)
                #rawCapture = PiRGBArray(camera, size=(640, 480))
                rawCapture = PiRGBArray(camera, size=(1280, 960))
                
                # initialize the next time to dictate a command to now
                next_command_time = time.time()
                prev_loc_diff = [0,0]
                # capture frames from the camera
                for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
                    # grab the raw NumPy array representing the image
                    image_array = frame.array

                    # show the frame, detect shapes, and calculate difference in locations
                    # between laser and target.
                    location_difference = self.detect(image_array)
                    
                    if location_difference is not None:
                        laser_moved = abs(location_difference[0] - prev_loc_diff[0]) > 15 \
                           or abs(location_difference[1] - prev_loc_diff[1]) > 15
                        
                        # If the laser hasn't moved since our last command, give it time to do so
                        if not laser_moved:
                            print('laser hasn\'t moved enough to dictate a new command')
                        # Speak commands every N seconds
                        elif time.time() > next_command_time:
                            print("Location difference is " + str(location_difference))
                            command = None
                            if abs(location_difference[0]) < self.hit_radius_px and abs(location_difference[1]) < self.hit_radius_px:
                                #command = "move reset"
                                print("HIT TARGET!")
                                new_led = random.choice(self.gpio_pins)
                                while new_led == self.lit_gpio_pin:
                                    new_led = random.choice(self.gpio_pins)
                                gpio.output(self.lit_gpio_pin, gpio.LOW)
                                gpio.output(new_led, gpio.HIGH)
                                self.lit_gpio_pin = new_led
                                rawCapture.truncate(0)
                                continue
                            elif abs(location_difference[0]) > abs(location_difference[1]):
                                # Seems to be ~7px per degree of movement of the pan-tilt
                                units = int(abs(location_difference[0]) / 7)
                                units = str(units)
                                if location_difference[0] > 0:
                                    #command = "move left " + units
                                    command = "move left"
                                else:
                                    #command = "move right " + units
                                    command = "move right"
                            else:
                                # Seems to be ~7px per degree of movement of the pan-tilt
                                units = int(abs(location_difference[1]) / 7)
                                units = str(units)
                                if location_difference[1] > 0:
                                    #command = "move up " + units
                                    command = "move up"
                                else:
                                    #command = "move down " + units
                                    command = "move down"
                            
                            print(command)
                            polly_thread = threading.Thread(target=self.speak, args=(polly, command))
                            lex_thread = threading.Thread(target=self.send_to_lex, args=(polly, lex, command))
                            polly_thread.start()
                            lex_thread.start()
                            polly_thread.join()
                            lex_thread.join()
                            #self.speak(polly, command)
                            #self.send_to_lex(polly_client=polly, lex_client=lex, text=command)
                            
                            next_command_time = time.time() + self.command_interval
                            prev_loc_diff = location_difference
             
                    # clear the stream in preparation for the next frame
                    rawCapture.truncate(0)
                    
                    key = cv2.waitKey(10) & 0xFF
                    # if the `q` key was pressed in a cv2 window, break from the loop
                    if key == ord("q"):
                        gpio.output(self.lit_gpio_pin, gpio.LOW)
                        break
            finally:
                gpio.output(self.lit_gpio_pin, gpio.LOW)
                cv2.destroyAllWindows()


if __name__ == '__main__':
    tracker = LaserTracker()
    tracker.run()
