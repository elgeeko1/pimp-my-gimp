#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo'
#########

# system libraries
import time
import datetime
import sys
import os
import math

# adafruit circuitpython libraries
import board
import neopixel

# GPIO libraries
import RPi.GPIO as GPIO

# audio libraries
from pydub import AudioSegment
from pydub.playback import play

# webserver libraries
from flask import Flask, request, render_template
from flask import send_from_directory  # send raw file
from flask import jsonify  # graphing

# maths for graphing
import pandas as pd
import numpy as np
from scipy.interpolate import interp1d

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18
# NeoPixel total number of NeoPixels in the array
PIXEL_COUNT = 163
# NeoPixel idle color
COLOR_IDLE = (0, 64, 64)

# Encoder GPIO pin
ENCODER_PIN = 12  # GPIO 12 / pin 32
# Encoder window length to remember, in unit of Encoder pulses.
ENCODER_WINDOW_PULSES = 20
# Encoder counts per revolution of the wheel
ENCODER_PULSES_PER_REV = 4
# Encoder pulses per linear foot
# wheel diameter is 7.5", so circumference is pi * 7.5
ENCODER_PULSES_PER_FOOT = float(ENCODER_PULSES_PER_REV) / (math.pi * (7.5/12.0))
# Encoder count. Updated asynchronously.
ENCODER_COUNT = 0.0
# Graph of encoder speed (timestamp, position). Updated asynchronously
ENCODER_GRAPH = []

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


def smooth_timeseries(timestamps: np.array, 
                      values: np.array, 
                      window_size: int, 
                      interp_spacing_s: float) -> list[(float, float)]:
    """
    Smooths a given time series data using linear interpolation followed by a moving average filter.
    
    Parameters:
    - timestamps: A numpy array of timestamps (in seconds since epoch time).
    - values: A numpy array of corresponding values.
    - window_size: The size of the moving average window, in samples. This determines the smoothing degree.
    - interp_spacing_s: The spacing in seconds for interpolation. Determines the interval of the resulting timestamps.
    
    Returns:
    - A list of tuples containing smoothed timestamps and their corresponding smoothed data values.
    
    Note:
    - The returned timestamps are interpolated based on the provided interp_spacing_s, and are not the same as the original timestamps.
    """
    
    # Generate new equispaced timestamps based on interp_spacing_s
    interpolated_timestamps = np.arange(timestamps[0], timestamps[-1], interp_spacing_s)

    # Create a linear interpolation function for the given timestamps and values
    f = interp1d(timestamps, values, kind='linear', fill_value='extrapolate', bounds_error=False)
    
    # Calculate interpolated values for the newly generated equispaced timestamps
    interpolated_values = f(interpolated_timestamps)

    # Check if interpolated values are available, if not, return an empty list
    if len(interpolated_values) == 0:
        return np.array([]), np.array([])
    
    # Apply moving average filter on the interpolated values for smoothing
    smoothed_values = np.convolve(interpolated_values, np.ones(window_size)/window_size, mode='valid')
    
    # Adjust the start and end of the timestamps to match the length of smoothed_values due to convolution
    smoothed_timestamps = interpolated_timestamps[:len(smoothed_values)]
    
    # Return the valid timestamps with their corresponding smoothed values as a list of tuples
    return smoothed_timestamps, smoothed_values


# encoder init
def encoder_init():
    global ENCODER_COUNT
    global ENCODER_GRAPH
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ENCODER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(ENCODER_PIN, GPIO.RISING, callback=encoder_handler)
    ENCODER_COUNT = 0.0
    ENCODER_GRAPH.append((time.time(), ENCODER_COUNT))


# encoder edge event callback
# called automatically in a separate thread on encoder pulses
#   channel: event channel
def encoder_handler(channel: int):
    global ENCODER_COUNT
    global ENCODER_GRAPH
    ENCODER_COUNT += 1.0
    ENCODER_GRAPH.append((time.time(), ENCODER_COUNT))


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
        else:
            # unknown command -- do nothing
            pass
        return ""
    
    # speed graph endpoint
    @app.route("/speed")
    def speed():
        global ENCODER_GRAPH
        # if last encoder pulse is more than a second old,
        # assume zero velocity and append a datapoint to the graph
        if time.time() - ENCODER_GRAPH[-1][0] > 1.0:
            ENCODER_GRAPH.append((time.time(), ENCODER_COUNT))
        # trim to graph window by dropping old timestamps
        while len(ENCODER_GRAPH) > ENCODER_WINDOW_PULSES:
            ENCODER_GRAPH.pop(0)

        plotly_data =  {
            'type': 'scatter',
            'x': [],
            'y': [],
            'mode': 'lines'
        }
        # copy volatile array
        position = np.array(ENCODER_GRAPH)
        # calculate and smooth the derivative of the encoder position graph
        if len(position) >= 2:
            # Calculate the differences in x and y values
            differences = np.diff(position, axis=0)

            # Calculate the derivative using the difference method
            derivatives = differences[:, 1] / differences[:, 0]

            (x,y) = smooth_timeseries(position[1:,0], derivatives, 2, 0.33)
            plotly_data =  {
                'type': 'scatter',
                'x': x.tolist(),
                'y': y.tolist(),
                'mode': 'lines'
            }

        return jsonify(data = plotly_data)
    
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