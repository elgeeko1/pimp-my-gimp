#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo'
#########

import time
import sys

import board
import neopixel

from flask import Flask, request, render_template

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18

# total number of NeoPixels in the array
PIXEL_COUNT = 163

# should the program terminate (handles SIGINT, SIGHUP, SIGTERM)
TERMINATE = False


# initialize the pixels array
#   return: pixel array
def pixels_init() -> neopixel.NeoPixel:
    pixels = neopixel.NeoPixel(
        pin = PIXEL_PIN,
        n = PIXEL_COUNT,
        auto_write = False
    )
    pixels.fill((0,0,0))
    pixels.show()
    return pixels


# display a 'hello' (initialization) pattern
#   pixels: initialized pixel array
def pixels_display_hello(pixels: neopixel.NeoPixel):
    sequence = [(255,0,0), (0,255,0), (0,0,255)]
    for color in sequence:
        pixels.fill(color)
        pixels.show()
        time.sleep(0.25)
    pixels.fill((0,0,0))
    pixels.show()

# display a rotating 'cylon' pattern
#   pixels: initialized pixel array
#   count:  number of cycles
def pixels_cylon(pixels: neopixel.NeoPixel, count:int = 1):
    pixels.fill((0,0,0))
    pixels.show()

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
                #time.sleep(0.005)

    pixels.fill((0,0,0))
    pixels.show()

# display a colorful strobe pattern
#   pixels: initialized pixel array
#   count:  number of strobes
def pixels_strobe(pixels: neopixel.NeoPixel, count:int = 10):
    pixels.fill((0,0,0))
    pixels.show()
    for n in range(count):
        for color in [(255,0,0),(0,255,0),(0,0,255)]:
            pixels.fill(color)
            pixels.show()
            time.sleep(0.025)
            pixels.fill((0,0,0))
            pixels.show()
            time.sleep(0.025)


# display a solid color
#   pixels: initialized pixel array
#   color:  color to display
def pixels_solid(pixels: neopixel.NeoPixel, color: tuple = (0, 64, 64)):
    pixels.fill(color)
    pixels.show()


# run the web server - blocking method
#   pixels: initialized pixel array
def run_web_server(pixels: neopixel.NeoPixel):
    print("Starting Flask server.")
    app = Flask(__name__)

    @app.route("/")
    def index():
        return render_template('index.html')
    
    @app.route("/command")
    def command():
        if request.args.get("strobe"):
            pixels_strobe(pixels)
        if request.args.get("cylon"):
            pixels_cylon(pixels)
        pixels_solid(pixels)
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
        run_web_server(pixels)
        rcode = 0
    finally:
        pixels_solid((0,0,0))
        pixels.deinit()
        print("Application exiting")
    sys.exit(rcode)


if __name__ == '__main__':
    main()