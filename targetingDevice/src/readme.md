
On Raspberry PI:
----------------
Make sure Python uses OpenSSL 1.0.2+

Create things: python manage_things.py --region us-east-1 create
Listen for things: python laser_guidance_thing.py --region us-east-1

In laser_guidance_movement.py, implement move_guidance(xdelta, ydelta) to move arm.

Lambda Functions:
-----------------
Simplified Lambda method that needs to Alexa-fied: alexa_lambda.py
You can test method with: test_alexa_lambda.py

