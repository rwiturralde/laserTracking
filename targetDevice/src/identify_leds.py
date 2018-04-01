import RPi.GPIO as GPIO
import time


GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)

leds = [4, 18, 23, 24]

for led in leds:
    GPIO.setup(led, GPIO.OUT)
    print "Turning on " + str(led)
    GPIO.output(led, GPIO.HIGH)
    time.sleep(2)
    GPIO.output(led, GPIO.LOW)


