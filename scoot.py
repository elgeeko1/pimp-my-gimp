import time
import board
import neopixel
import numpy
from flask import Flask

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18

# total number of NeoPixels in the array
PIXEL_COUNT = 163

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
def pixels_display_hello(pixels: neopixel.NeoPixel):
    print("<p>pixels_display_hello</p>")
    sequence = [(255,0,0), (0,255,0), (0,0,255)]
    for color in sequence:
        pixels.fill(color)
        pixels.show()
        time.sleep(0.25)
    pixels.fill((0,0,0))
    pixels.show()
    print("<p>pixels_display_hello complete</p>")

def pixels_cylon(pixels: neopixel.NeoPixel, count:int = 1):
    print("<p>pixels_display_cylon</p>")

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
                time.sleep(0.010)

    pixels.fill((0,0,0))
    pixels.show()
    print("<p>pixels__display_cylon complete</p>")

def pixels_seizure(pixels: neopixel.NeoPixel, count:int = 10):
    pixels.fill((0,0,0))
    pixels.show()
    # flash
    for n in range(count):
        for color in [(255,0,0),(0,255,0),(0,0,255)]:
            pixels.fill(color)
            pixels.show()
            time.sleep(0.025)
            pixels.fill((0,0,0))
            pixels.show()
            time.sleep(0.025)

def run_web_server(pixels: neopixel.NeoPixel):
    app = Flask(__name__)

    @app.route("/")
    def hello_world():
        pixels_seizure(pixels)
        pixels_cylon(pixels)
        return "<p>Hello, World!</p>"
    
    app.run(host="192.168.1.38", port=80)

def main():
    pixels = pixels_init()
    try:
        pixels_display_hello(pixels)
        pixels.fill((0, 64, 64)) # teal
        pixels.show()
        run_web_server(pixels)
    finally:
        pixels.fill((0,0,0))
        pixels.show()
        pixels.deinit()

if __name__ == '__main__':
    main()