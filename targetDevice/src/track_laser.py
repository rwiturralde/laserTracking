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

'''
Uses a camera to track a laser pointer and instruct it, via dictation,
to move toward a destination.
'''
class LaserTracker(object):

    def __init__(self):
        # How often we'll dictate commands
        self.command_interval = 5 #seconds
        self.hit_radius_px = 120 # pixles
        self.defaultRegion = 'us-east-1'
        self.defaultPollyEndpoint = 'https://polly.us-east-1.amazonaws.com'
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
    Use a given AWS Polly boto3 client to dictate a string of text.
    Can optionally specify the file format for the audio and the dictation voice
    '''
    def speak(self, polly, text, format='ogg_vorbis', voice='Joanna'):
        now = time.time()
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
                soundfile.close()
                os.system('omxplayer ' + filename)

        print("Spoke audio in " + str(time.time() - now) + " seconds")


    def detect(self, frame):
        # Blur to smooth edges of shapes
        blurred = cv2.GaussianBlur(frame, (11,11), 0)
        #hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        hsv_blurred = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        # define the lower and upper boundaries
        # in the HSV color space
        #LASER_MIN = np.array([0, 0, 230])
        #LASER_MAX = np.array([8, 115, 255])
        #lower_red = np.array([0, 0, 10])
        #upper_red = np.array([10, 255, 255])
        lower_green = np.array([29, 86, 6])
        upper_green = np.array([64, 255, 255])
        lower_blue = np.array([110,50,50])
        upper_blue = np.array([130,255,255])
        
        # construct a mask for the colors, then perform
        # a series of dilations and erosions to remove any small
        # blobs left in the mask
        #red_mask = cv2.inRange(hsv_img, lower_red, upper_red)
        green_mask = cv2.inRange(hsv_blurred, lower_green, upper_green)
        green_mask = cv2.erode(green_mask, None, iterations=2)
        green_mask = cv2.dilate(green_mask, None, iterations=2)
        blue_mask = cv2.inRange(hsv_blurred, lower_blue, upper_blue)
        #blue_mask = cv2.erode(blue_mask, None, iterations=2)
        #blue_mask = cv2.dilate(blue_mask, None, iterations=2)

        # find contours in the mask and initialize the current
        # (x, y) center of the ball
        green_cnts = cv2.findContours(green_mask.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)[-2]
        blue_cnts = cv2.findContours(blue_mask.copy(), cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE)[-2]
        green_center = None
        blue_center = None

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
        
        if len(blue_cnts) > 0:
            # find the largest contour in the mask, then use
            # it to compute the minimum enclosing circle and
            # centroid
            c = max(blue_cnts, key=cv2.contourArea)
            ((x, y), radius) = cv2.minEnclosingCircle(c)
            M = cv2.moments(c)
            if "m00" in M and M["m00"] > 0:
                blue_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))
            else:
                blue_center = (x,y)

            # only proceed if the radius meets a minimum size
            if radius > 10:
                # draw the circle and centroid on the frame,
                cv2.circle(frame, (int(x), int(y)), int(radius),
                        (0, 255, 255), 2)
                cv2.circle(frame, blue_center, 5, (0, 0, 255), -1)

        cv2.imshow('frame',frame)
        
        diff = None
        if green_center is not None and blue_center is not None:
            diff = np.subtract(blue_center, green_center)
        
        return diff
    

    def run(self):
        #initialize polly connection
        polly = self.connectToPolly()
        # initialize the camera and grab a reference to the raw camera capture
        # with-block ensures camera.close() is called upon exit.
        with PiCamera() as camera:
            try:
                camera.resolution = (640, 480)
                camera.framerate = 35
                # allow the camera to warmup
                time.sleep(0.1)
                rawCapture = PiRGBArray(camera, size=(640, 480))
                
                # initialize the next time to dictate a command to now
                next_command_time = time.time()
                # capture frames from the camera
                for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
                    # grab the raw NumPy array representing the image
                    image_array = frame.array

                    # show the frame, detect shapes, and calculate difference in locations
                    # between laser and target.
                    location_difference = self.detect(image_array)
                    
                    # Speak commands every N seconds
                    if time.time() > next_command_time:        
                        if location_difference is not None:
                            print("Location difference is " + str(location_difference))
                            command = None
                            if abs(location_difference[0]) < self.hit_radius_px and abs(location_difference[1]) < self.hit_radius_px:
                                command = "hit"                            
                            elif abs(location_difference[0]) > abs(location_difference[1]):
                                if location_difference[0] > 0:
                                    command = "left"
                                else:
                                    command = "right"
                            else:
                                if location_difference[1] > 0:
                                    command = "up"
                                else:
                                    command = "down"
                            
                            print(command)
                            self.speak(polly, command)
                        next_command_time = time.time() + self.command_interval
             
                    # clear the stream in preparation for the next frame
                    rawCapture.truncate(0)
                    
                    key = cv2.waitKey(10) & 0xFF
                    # if the `q` key was pressed in a cv2 window, break from the loop
                    if key == ord("q"):
                            break
            finally:
                cv2.destroyAllWindows()


if __name__ == '__main__':
    tracker = LaserTracker()
    tracker.run()
