#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo'
#########

# system libraries
import threading
import time
import sys
import os
import math
from typing import Callable

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
import numpy

# telegraf
import requests
from requests_futures.sessions import FuturesSession
import urllib3

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
# Encoder speed smoothing coefficient (for exponential moving average)
ENCODER_SMOOTHING = 0.75

# Define the URL for the HTTP listener of Telegraf
TELEGRAPH_URL = "http://telegraf:8186/telegraf"

class TimeStampedCircularBuffer:
    """
    A circular buffer that holds timestamped data entries.
    Once the buffer reaches its capacity, it starts overwriting the oldest data.
    """
    def __init__(self, capacity: int):
        """
        Initializes the buffer with a given capacity.
        
        :param capacity: The maximum number of timestamped data entries the buffer can hold.
        """
        self._capacity = capacity
        self._buffer = numpy.empty((0, 2), float)  # Initialize an empty 2D array for timestamp and data
        self._head = 0  # Points to the start of the buffer (write head)

    def append(self, timestamp: float, value: float) -> None:
        """
        Appends a new timestamped data entry to the buffer.

        :param timestamp: The timestamp of the data point.
        :param value: The data value to store.
        """
        if self._buffer.shape[0] < self._capacity:
            self._buffer = numpy.vstack((self._buffer, numpy.array([timestamp, value])))
        else:
            self._buffer[self._head] = [timestamp, value]
            self._head = (self._head + 1) % self._capacity

    def last(self) -> numpy.ndarray:
        """
        Returns the last appended data entry.

        :return: The last data entry in the buffer.
        """
        return self._buffer[(self._head - 1) % self._capacity]

    def values(self) -> numpy.ndarray:
        """
        Retrieves all the timestamped data entries in the buffer, ordered by the time they were added.
        This method takes into account the circular nature of the buffer to return the values in the correct order.

        :return: A numpy array of timestamped data entries, where each entry is a [timestamp, value] pair.
        """
        return numpy.roll(self._buffer, -self._head, axis=0)


class ExponentialSmoothing:
    """
    Exponential smoothing algorithm for time series data.
    """
    def __init__(self, alpha: float = 0.5):
        """
        Initializes the exponential smoothing filter.

        :param alpha: The smoothing factor, a value between 0 and 1.
        """
        self._alpha = alpha
        self._last_smoothed = None

    def smooth(self, value: float) -> float:
        """
        Applies exponential smoothing to the given value.

        :param value: The data value to be smoothed.
        :return: The smoothed data value.
        """
        if self._last_smoothed is None:
            self._last_smoothed = value
        else:
            self._last_smoothed = self._alpha * value + (1 - self._alpha) * self._last_smoothed

        return self._last_smoothed
    
    def value(self) -> float:
        """
        Returns the last smoothed value.

        :return: The last smoothed data value.
        """
        return self._last_smoothed

class Trajectory:
    """
    The Trajectory class calculates and stores the position and speed of an object over time.
    It uses a TimeStampedCircularBuffer to maintain a fixed-size window of the latest position and speed data points
    and applies exponential smoothing to the speed data to reduce noise and variability in the measurements.
    """

    def __init__(
            self,
            window_size: int,
            alpha: float = 0.5,
            step_callback: Callable[[float, float, float], None] = lambda timestamp, position, speed : None):
        """
        Initializes the Trajectory with a specified window size for the buffers and a smoothing factor for speed calculation.

        :param window_size: The maximum number of entries for the position and speed graphs.
        :param alpha: The smoothing factor used for exponential smoothing of the speed data.
        :param step_callback: Callback to execute on every trajectory step.
        """
        self._last_timestamp = time.time()  # Stores the timestamp of the last update
        self._last_position = 0.0  # Stores the last calculated position
        self._last_speed = 0.0  # Stores the last calculated speed
        self._position_graph = TimeStampedCircularBuffer(window_size)  # Circular buffer for position data
        self._speed_graph = TimeStampedCircularBuffer(window_size)  # Circular buffer for speed data
        self._speed_filter = ExponentialSmoothing(alpha)  # Exponential smoothing filter for speed
        self._step_callback = step_callback

    def step(self, step_pulses: float = 1.0, offset_s: float = 0.0):
        """
        Updates the position and speed based on the step pulses received since the last update.

        :param step_pulses: The number of pulses since the last update, which is proportional to the distance moved.
        :param offset_s: The time offset in seconds to be added to the current time, for timestamping the update.
        """
        timestamp = time.time() + offset_s
        dt = timestamp - self._last_timestamp
        new_position = self._last_position + step_pulses
        new_speed = self._speed_filter.smooth(step_pulses / dt)
        self._position_graph.append(timestamp, new_position)
        self._speed_graph.append(timestamp, new_speed)
        self._last_timestamp = timestamp
        self._last_position = new_position
        self._last_speed = new_speed
        self._step_callback(timestamp, new_position, new_speed)

    def position(self) -> (float, float):
        """
        Returns the last recorded position and its associated timestamp.

        :return: A tuple containing the last timestamp and the last position.
        """
        return self._last_timestamp, self._last_position

    def positions(self) -> numpy.ndarray:
        """
        Retrieves all the recorded positions from the position graph.

        :return: A numpy array of timestamped position entries.
        """
        return self._position_graph.values()

    def speed(self) -> (float, float):
        """
        Returns the last recorded speed and its associated timestamp.

        :return: A tuple containing the last timestamp and the last speed.
        """
        return self._last_timestamp, self._last_speed

    def speeds(self) -> numpy.ndarray:
        """
        Retrieves all the recorded speeds from the speed graph.

        :return: A numpy array of timestamped speed entries.
        """
        return self._speed_graph.values()


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
    trajectory = Trajectory(ENCODER_WINDOW_PULSES, ENCODER_SMOOTHING)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(ENCODER_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(ENCODER_PIN, GPIO.RISING, callback=encoder_handler)

# encoder edge event callback
# called automatically in a separate thread on encoder pulses
#   channel: event channel
def encoder_handler(channel: int):
    global trajectory
    trajectory.step(1.0)

# executes periodically to determine of speed is zero, and adds zero points
# to the trajectory
def encoder_check_speed():
    global trajectory
    # if last encoder pulse was seen more than stopped_threshold_s seconds ago,
    # assume zero spee and append a zero step to the encoder graph.
    # introduce latency of stopped_threshold_s / 2 to account for encoder pulses
    # that may arrive soon, resulting in artificially large reported speeds
    stopped_threshold_s = 1.0
    while True:
        timestamp, _ = trajectory.speed()
        if time.time() - timestamp > stopped_threshold_s:
            trajectory.step(0.0, -(stopped_threshold_s / 2.0))
        time.sleep(stopped_threshold_s)

def telegraf_post_datapoint(timestamp: float, position: float, speed: float) -> None:
    global telegraf_session

    # Convert the timestamp to nanoseconds
    timestamp_ns = int(timestamp * 1e9)
    
    telegraf_session.post(
        TELEGRAPH_URL,
        data = f"distance_ft value={position / ENCODER_PULSES_PER_FOOT} {timestamp_ns}",
        headers = {'Content-Type': 'application/x-www-form-urlencoded'})
    telegraf_session.post(
        TELEGRAPH_URL,
        data = f"speed_ft_s value={speed / ENCODER_PULSES_PER_FOOT} {timestamp_ns}",
        headers = {'Content-Type': 'application/x-www-form-urlencoded'})

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
        global trajectory
        speed_graph = trajectory.speeds()
        plotly_data =  {
            'type': 'scatter',
            'x': speed_graph[:, 0].tolist() if len(speed_graph) else [],
            'y': speed_graph[:, 1].tolist() if len(speed_graph) else [],
            'mode': 'lines'
        }
        return jsonify(data = plotly_data)
    
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host="0.0.0.0", port=80)


# global variables
trajectory = Trajectory(ENCODER_WINDOW_PULSES, ENCODER_SMOOTHING, telegraf_post_datapoint)
telegraf_session = FuturesSession()

# application entrypoint
def main():
    pixels = pixels_init()
    rcode = 1

    try:
        print("Application starting")
        pixels_display_hello(pixels)
        pixels_solid(pixels)

        encoder_init()
        encoder_check_speed_thread = threading.Thread(target=encoder_check_speed)
        encoder_check_speed_thread.daemon = True
        encoder_check_speed_thread.start()

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