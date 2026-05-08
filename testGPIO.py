import RPi.GPIO as GPIO

LEDPIN = 16
GPIO.setmode(GPIO.BCM)
GPIO.setup(LEDPIN,GPIO.OUT)
print("LED 1")
GPIO.output(LEDPIN,False)