#! /usr/bin/env python
import argparse
import os, boto3, io, sys, time, json
from contextlib import closing
import cv2
import numpy as np
from picamera.array import PiRGBArray
from picamera import PiCamera

'''
Uses a camera to track a laser pointer and instruct it, via dictation,
to move toward a destination.
'''
class LaserTracker(object):

    def __init__(self):
        # How often we'll dictate commands
        self.command_interval = 2 #seconds
        self.hit_radius_px = 50 # pixels
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
    Create a boto3 AWS Lex client
    '''
    def connectToLex(self, regionName=None):
        regionName = regionName if regionName is not None else self.defaultRegion
        print("Connecting to LEX in " + regionName)
        return boto3.client('lex-runtime', region_name=regionName)
    
    '''
    Create a boto3 AWS Rekognition client
    '''
    def connectToRekognition(self, regionName=None):
        regionName = regionName if regionName is not None else self.defaultRegion
        print("Connecting to Rekognition in " + regionName)
        return boto3.client('rekognition', region_name=regionName)

    '''
    Use a given AWS Polly boto3 client to dictate a string of text.
    Can optionally specify the file format for the audio and the dictation voice
    '''
    def speak(self, polly, text, format='ogg_vorbis', voice='Joanna'):
        now = time.time()
        filename = 'tmp.ogg'
        #filename = text.replace(' ', '_') + '.ogg'
        # look for cached result
        #if os.path.isfile(filename):
        #    print("Previous audio file found. Playing: " + filename)
        #    os.system('omxplayer ' + filename)
        #else:
            # No cached result, so fetch from Polly
        #print("No previous result for audio filename: " + filename + ". Calling Polly...")
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
    def send_to_lex(self, polly, lex, text='Hello world', botName='testing', botAlias='test_alias', userId='targetingDefault', voice='Joanna', \
                          lexContentType='audio/x-l16; sample-rate=16000; channel-count=1'):
        
        lex_parsed = False
        
        while not lex_parsed:
            start = time.time()
            print("Calling Polly for command " + text)
            resp = polly.synthesize_speech(OutputFormat='pcm', SampleRate='16000', Text=text, VoiceId=voice)
            print("Sending Polly response to Lex for command " + text)
            with closing(resp["AudioStream"]) as stream:
                lex_resp = lex.post_content(botName=botName, botAlias=botAlias, userId=userId, contentType=lexContentType, inputStream=stream.read())
                print("Fetched audio and posted to Lex in " + str(time.time() - start) + " seconds")
                
                if lex_resp['dialogState'] == 'ElicitIntent':
                    print('Lex failed to parse command: ' + text + '. Retrying... \nResponse: ' + lex_resp)
                else:
                    lex_parsed = True
    

    def run(self):
        #initialize rekognition connection
        rekognition = self.connectToRekognition()
        # initialize the camera and grab a reference to the raw camera capture
        # with-block ensures camera.close() is called upon exit.
        with PiCamera(resolution = (640, 480),framerate = 35) as camera:
            try:
                camera.hflip = True
                camera.vflip = True
                # allow the camera to warmup
                time.sleep(0.1)
                camera.start_preview()
                
                # initialize the next time to dictate a command to now
                next_command_time = time.time()
                prev_loc_diff = [0,0]
                byteStream = io.BytesIO()
                prev_time = time.time()
                stop_time = time.time() + (60 * 5)
                # capture frames from the camera
                for frame in camera.capture_continuous(byteStream, format='jpeg'):
                    byteStream.truncate()
                    byteStream.seek(0)
                    
                    now = time.time()
                    
                    if (now > prev_time + 3):
                        rekognition_resp = rekognition.detect_labels(Image={'Bytes': byteStream.getvalue()})
                        print(rekognition_resp)
                        prev_time = now
                    
                    if now > stop_time:
                        break
             
            finally:
                camera.stop_preview()
                


if __name__ == '__main__':
    tracker = LaserTracker()
    tracker.run()

