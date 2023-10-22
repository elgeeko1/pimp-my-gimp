#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo'
#########

# system libraries
import time
import sys
import os

# adafruit circuitpython libraries
import board
import neopixel

# GPIO libraries
import RPi.GPIO as GPIO

# audio libraries
from pydub import AudioSegment
from pydub.playback import play

# webserver libraries
from flask import Flask, request, render_template, send_from_directory

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18
# NeoPixel total number of NeoPixels in the array
PIXEL_COUNT = 163
# NeoPixel idle color
COLOR_IDLE = (0, 64, 64)

# Encoder GPIO pin
ENCODER_PIN = 12  # GPIO 12 / pin 32
# Encoder count. Updated asynchronously.
ENCODER_COUNT = 0
# Timestamp of last encoder event. Updated asynchronously.
ENCODER_TIMESTAMP = time.time()
# Most recently recorded encoder speed, in pulses per second (PPS).
# Updated asyncronously.
ENCODER_PPS = 0


# initialize the pixels array
#   return: pixel array
def pixels_init() -> neopixel.NeoPixel:
    pixels = neopixel.NeoPixel(
        pin = PIXEL_PIN,
        n = PIXEL_COUNT,
        auto_write = False
    )
    pixels_solid(pixels, (0,0,0))
    return pixels


# display a 'hello' (initialization) pattern
#   pixels: initialized pixel array
def pixels_display_hello(pixels: neopixel.NeoPixel):
    pixels_solid(pixels, (0,0,0))
    sequence = [(255,0,0), (0,255,0), (0,0,255)]
    for color in sequence:
        pixels_solid(pixels, color)
        time.sleep(0.250)
    pixels_solid(pixels, (0,0,0))


# display a rotating 'cylon' pattern
#   pixels: initialized pixel array
#   count:  number of cycles
def pixels_cylon(pixels: neopixel.NeoPixel, count:int = 1):
    pixels_solid(pixels, (0,0,0))

    # rotate cylon pattern
    for n in range(count):
        for color in [(1,0,0),(0,1,0),(0,0,1)]:
            # initial pattern
            for pixel in range(PIXEL_COUNT):
                value = int((1 - abs((PIXEL_COUNT / 2) - pixel) / (PIXEL_COUNT / 2)) * 255)
                pixels[pixel] = tuple(value * k for k in color)

            for cycle in range(PIXEL_COUNT):
                last_pixel = pixels[0]
                for pixel in range(PIXEL_COUNT - 1):
                    pixels[pixel] = pixels[pixel+1]
                pixels[PIXEL_COUNT-1] = last_pixel
                pixels.show()

    pixels_solid(pixels, (0,0,0))

# display a colorful strobe pattern
#   pixels: initialized pixel array
#   count:  number of strobes
def pixels_strobe(pixels: neopixel.NeoPixel, count:int = 10):
    for n in range(count):
        for color in [(255,0,0),(0,255,0),(0,0,255)]:
            pixels_flash(pixels, color)


# display a fill color that flashes on then off
#   pixels: initialized pixel array
#   color:  color to display
#   count:  number of flashes
def pixels_flash(pixels: neopixel.NeoPixel, color:tuple = (255,255,255), count:int = 1):
    for n in range(count):
        pixels_solid(pixels, (0,0,0))
        time.sleep(0.150)
        pixels_solid(pixels, color)
        # sleep if not last flash
        if n + 1 < count:
            time.sleep(0.0200)


# display a solid color
#   pixels: initialized pixel array
#   color:  color to display
def pixels_solid(pixels: neopixel.NeoPixel, color: tuple = COLOR_IDLE):
    pixels.fill(color)
    pixels.show()


# encoder init
def encoder_init():
    global ENCODER_COUNT
    global ENCODER_TIMESTAMP
    global ENCODER_PPS
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ENCODER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(ENCODER_PIN, GPIO.RISING, callback=encoder_handler)
    ENCODER_COUNT = 0
    ENCODER_TIMESTAMP = time.time()
    ENCODER_PPS = 0


# encoder edge event callback
# called automatically in a separate thread on encoder pulses
#   channel: event channel
def encoder_handler(channel: int):
    global ENCODER_COUNT
    global ENCODER_TIMESTAMP
    global ENCODER_PPS
    ENCODER_COUNT = ENCODER_COUNT + 1
    previous_timestamp = ENCODER_TIMESTAMP
    ENCODER_TIMESTAMP = time.time()
    ENCODER_PPS = 1.0 / (ENCODER_TIMESTAMP - previous_timestamp)


# run the web server - blocking method
#   pixels: initialized pixel array
def run_web_server(pixels: neopixel.NeoPixel):
    print("Starting Flask server.")
    app = Flask(__name__)

    # read first milliseconds from alert sound
    # the range of acoustic interest is determined empirically
    alarm_sound = AudioSegment.from_mp3("static/sounds/red-alert.mp3")[100:1250]

    # return index page
    @app.route("/")
    def index():
        return render_template('index.html')

    # return favicon and manifest    
    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(
            os.path.join(app.root_path, 'static/images'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon')
    @app.route("/manifest.json")
    def manifest():
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'manifest.json',)
    
    # command endpoint: route argument to command
    @app.route("/command")
    def command():
        if request.args.get("strobe"):
            pixels_strobe(pixels)
            pixels_solid(pixels, COLOR_IDLE)
        elif request.args.get("cylon"):
            pixels_cylon(pixels)
            pixels_solid(pixels, COLOR_IDLE)
        elif request.args.get("alarm"):
            for count in range(4):
                pixels_flash(pixels, (255,255,255), 2)
                pixels_flash(pixels, (255,0,0), 1)
                play(alarm_sound)
            pixels_solid(pixels, COLOR_IDLE)
        elif request.args.get("off"):
            pixels_solid(pixels, (0,0,0))
        elif request.args.get("speed"):
            print("ENCODER_PPS = " + str(ENCODER_PPS))
        else:
            # unknown command -- do nothing
            pass
        return ""
    
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host="0.0.0.0", port=80)

# application entrypoint
def main():
    pixels = pixels_init()
    rcode = 1
    try:
        print("Application starting")
        pixels_display_hello(pixels)
        pixels_solid(pixels)
        encoder_init()
        run_web_server(pixels)
        rcode = 0
    finally:
        pixels_solid(pixels, (0,0,0))
        pixels.deinit()
        GPIO.cleanup()
        print("Application exiting")
    sys.exit(rcode)


if __name__ == '__main__':
    main()