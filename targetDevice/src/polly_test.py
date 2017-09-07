import os, boto3
from contextlib import closing

defaultRegion = 'us-east-1'
defaultUrl = 'https://polly.us-east-1.amazonaws.com'

def connectToPolly(regionName=defaultRegion, endpointUrl=defaultUrl):
    return boto3.client('polly', region_name=regionName, endpoint_url=endpointUrl)

def speak(polly, text, format='ogg_vorbis', voice='Joanna'):
    resp = polly.synthesize_speech(OutputFormat=format, Text=text, VoiceId=voice)
    
    with closing(resp["AudioStream"]) as stream:
        # mp3 files were playing the with end clipped via omxplayer.
        soundfile = open('sound.ogg', 'wb')
        soundfile.write(stream.read())
        soundfile.close()
        os.system('omxplayer sound.ogg') 
        #os.remove('sound.ogg')

polly = connectToPolly()
speak(polly, "Frank sucks, big league!")
