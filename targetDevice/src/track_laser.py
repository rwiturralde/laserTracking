#! /usr/bin/env python
import argparse
#from cv2 import cv
import cv2
import sys
import numpy as np
from picamera.array import PiRGBArray
from picamera import PiCamera
import time

class LaserTracker(object):

    def __init__(self):
        print("test")
        return

    def detect(self, frame):
        blurred = cv2.GaussianBlur(frame, (11,11), 0)
        hsv_img = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        # blur to smooth edges
        hsv_blurred = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)
        # define the lower and upper boundaries
        # in the HSV color space
        #LASER_MIN = np.array([0, 0, 230])
        #LASER_MAX = np.array([8, 115, 255])
        lower_red = np.array([0, 0, 10])
        upper_red = np.array([10, 255, 255])
        
        lower_green = np.array([29, 86, 6])
        upper_green = np.array([64, 255, 255])
        
        lower_blue = np.array([110,50,50])
        upper_blue = np.array([130,255,255])
        
        # construct a mask for the colors, then perform
        # a series of dilations and erosions to remove any small
        # blobs left in the mask
        #frame_threshed = cv2.inRange(hsv_img, LASER_MIN, LASER_MAX)
        red_mask = cv2.inRange(hsv_img, lower_red, upper_red)
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
            green_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

            # only proceed if the radius meets a minimum size
            if radius > 10:
                # draw the circle and centroid on the frame,
                # then update the list of tracked points
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
            blue_center = (int(M["m10"] / M["m00"]), int(M["m01"] / M["m00"]))

            # only proceed if the radius meets a minimum size
            if radius > 10:
                # draw the circle and centroid on the frame,
                # then update the list of tracked points
                cv2.circle(frame, (int(x), int(y)), int(radius),
                        (0, 255, 255), 2)
                cv2.circle(frame, blue_center, 5, (0, 0, 255), -1)

        # Bitwise-AND mask and original image
        #red_result = cv2.bitwise_and(frame,frame, mask= red_mask)
        #green_result = cv2.bitwise_and(frame,frame, mask= green_mask)
        #blue_result = cv2.bitwise_and(frame,frame, mask= blue_mask)

        cv2.imshow('frame',frame)
        #cv2.imshow('red_mask', red_mask)
        #cv2.imshow('red_result', red_result)
        cv2.imshow('green_mask', green_mask)
        cv2.imshow('blue_mask', blue_mask)

        return 0, 0

    def run(self):
        sys.stdout.write("Using OpenCV version: {0}\n".format(cv2.__version__))

        # Set up the camer captures
        # initialize the camera and grab a reference to the raw camera capture
        camera = PiCamera()
        camera.resolution = (640, 480)
        camera.framerate = 15
        #time.sleep(.5)
        rawCapture = PiRGBArray(camera, size=(640, 480))

        # capture frames from the camera
        for frame in camera.capture_continuous(rawCapture, format="bgr", use_video_port=True):
            # grab the raw NumPy array representing the image, then initialize the timestamp
            # and occupied/unoccupied text
            image_array = frame.array

            # show the frame
            self.detect(image_array)
     
            # clear the stream in preparation for the next frame
            rawCapture.truncate(0)
            
            key = cv2.waitKey(10) & 0xFF
            # if the `q` key was pressed, break from the loop
            if key == ord("q"):
                    break

            #(laserx, lasery) = self.detect(frame)
            #sys.stdout.write("(" + str(laserx) + "," + str(lasery) + ")" + "\n")
            
        cv2.destroyAllWindows()


if __name__ == '__main__':
    tracker = LaserTracker()
    tracker.run()
