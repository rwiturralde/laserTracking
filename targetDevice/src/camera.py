#from picamera import PiCamera
#from time import sleep

#camera = PiCamera()
#camera.resolution = (512, 512)

#camera.start_preview()
#sleep(5)
#camera.capture('/home/pi/Desktop/capture.jpg')
#camera.stop_preview()

# import the necessary packages
from picamera.array import PiRGBArray
from picamera import PiCamera
import time
import cv2

# initialize the camera and grab a reference to the raw camera capture
camera = PiCamera()
rawCapture = PiRGBArray(camera)

# allow the camera to warmup
time.sleep(0.1)

# grab an image from the camera
camera.capture(rawCapture, format="bgr")
image = rawCapture.array

# display the image on screen and wait for a keypress
cv2.imshow("Image", image)
cv2.waitKey(0)