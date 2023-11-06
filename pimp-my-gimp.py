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
import colorsys

# GPIO libraries
import RPi.GPIO as GPIO

# audio libraries
from pydub import AudioSegment
from pydub.playback import play

# webserver libraries
from flask import Flask, request, render_template
from flask import send_from_directory  # send raw file
from flask import jsonify  # graphing
from flask_socketio import SocketIO, emit

# telegraf
from requests_futures.sessions import FuturesSession

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18
# NeoPixel total number of NeoPixels in the array
PIXEL_COUNT = 163
# NeoPixel idle color
COLOR_IDLE = (0, 0, 64)

# Encoder GPIO pin
ENCODER_PIN = 12  # GPIO 12 / pin 32
# Encoder counts per revolution of the wheel
ENCODER_PULSES_PER_REV = 4
# Encoder pulses per linear foot
# wheel diameter is 7.5", so circumference is pi * 7.5
ENCODER_PULSES_PER_FOOT = float(ENCODER_PULSES_PER_REV) / (math.pi * (7.5/12.0))
# Time since last encoder pulse after which the speed is assumed to be zero
ENCODER_SPEED_ZERO_THRESHOLD_S = 0.75
# Encoder speed smoothing coefficient (for exponential moving average)
ENCODER_SMOOTHING = 0.6

# Define the URL for the HTTP listener of Telegraf
TELEGRAPH_URL = "http://telegraf:8186/telegraf"


class ExponentialSmoothing:
    """
    Exponential smoothing algorithm for time series data.
    """
    def __init__(self, alpha: float = 0.5, zero_tolerance = -math.inf):
        """
        Initializes the exponential smoothing filter.

        :param alpha: The smoothing factor, a value between 0 and 1.
        :param zero_tolance: Threshold below which the absolute smoothed value should round to zero
        """
        self._alpha = alpha
        self._last_smoothed = None
        self._zero_tolerance = zero_tolerance

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
            if math.fabs(self._last_smoothed) < self._zero_tolerance:
                self._last_smoothed = 0.0

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
    Exponential smoothing is applied to speed data to reduce noise and variability in the measurements.
    """

    def __init__(self, alpha: float = 0.5):
        """
        Initializes the Trajectory with a specified window size for the buffers and a smoothing factor for speed calculation.

        :param alpha: The smoothing factor used for exponential smoothing of the speed data.
        """
        self._last_timestamp = time.time()  # Stores the timestamp of the last update
        self._last_position = 0.0  # Stores the last calculated position
        self._last_speed = 0.0  # Stores the last calculated speed
        self._speed_filter = ExponentialSmoothing(alpha, 0.001)  # Exponential smoothing filter for speed
        self._step_callbacks = []
        
    def register_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register a callback to be issued upon every trajectory step.

        :param callback: method witih signature (timestamp: float, position: float, speed: float) -> None
        """
        self._step_callbacks.append(callback)
       
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
        self._last_timestamp = timestamp
        self._last_position = new_position
        self._last_speed = new_speed

        # issue callbacks
        for callback in self._step_callbacks:
            callback(timestamp, new_position, new_speed)

    def position(self) -> (float, float):
        """
        Returns the last recorded position and its associated timestamp.

        :return: A tuple containing the last timestamp and the last position.
        """
        return self._last_timestamp, self._last_position

    def speed(self) -> (float, float):
        """
        Returns the last recorded speed and its associated timestamp.

        :return: A tuple containing the last timestamp and the last speed.
        """
        return self._last_timestamp, self._last_speed


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
                time.sleep(0.005)

            time.sleep(0.050) # give the CPU a break between colors

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


class ScootEncoder:
    # encoder init
    def __init__(self,
                 encoder_pin,
                 alpha: float = 0.5,
                 zero_speed_threshold_s = 0.01):
        self._trajectory = Trajectory(alpha)
        self._zero_speed_threshold_s = zero_speed_threshold_s
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(encoder_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(encoder_pin, GPIO.RISING, callback=self.encoder_handler)

        encoder_check_speed_thread = threading.Thread(target=self.encoder_check_speed)
        encoder_check_speed_thread.daemon = True
        encoder_check_speed_thread.start()

    # encoder edge event callback
    # called automatically in a separate thread on encoder pulses
    #   channel: event channel
    def encoder_handler(self, channel: int):
        self._trajectory.step(1.0)

    # executes periodically to determine of speed is zero, and adds zero points
    # to the trajectory
    def encoder_check_speed(self):
        # if time since last encoder pulse is greater than zero_speed_threshold_s,
        # assume zero spee and append a zero step to the encoder graph.
        # introduce latency of zero_speed_threshold_s / 2 to account for encoder pulses
        # that may arrive soon, resulting in artificially large reported speeds
        while True:
            timestamp, _ = self._trajectory.speed()
            if time.time() - timestamp > self._zero_speed_threshold_s:
                self._trajectory.step(0.0, -self._zero_speed_threshold_s)
            time.sleep(self._zero_speed_threshold_s)

    def register_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register a callback to be issued upon every trajectory step.

        :param callback: method witih signature (timestamp: float, position: float, speed: float) -> None
        """
        self._trajectory.register_callback(callback)


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

def websocket_post_datapoint(timestamp: float, position: float, speed: float) -> None:
    socketio.emit(
        'newdata', {
            'timestamp': math.ceil(timestamp * 1000),
            'position': position,
            'speed': speed },
        namespace='/trajectory')

# run the web server - blocking method
#   pixels: initialized pixel array
def run_web_server(pixels: neopixel.NeoPixel):
    print("Starting Flask server.")
    global socketio
    app = Flask(__name__)
    socketio = SocketIO(app, cors_allowed_origins = "*")

    # import sounds
    # the time window of acoustic interest is determined emprically
    sound_meltdown = AudioSegment.from_mp3("static/sounds/meltdown.mp3")[100:1250]
    sound_disco = AudioSegment.from_mp3("static/sounds/disco.mp3")[5000:9500]
    sound_underlight = AudioSegment.from_mp3("static/sounds/underlight.mp3")[250:6000]
    sound_lights_out = AudioSegment.from_mp3("static/sounds/lights-out.mp3")[4900:6250]

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
    
    # disco party!
    @app.route("/disco")
    def disco():
        thread = threading.Thread(target = lambda: play(sound_disco), daemon = True)
        thread.start()
        pixels_strobe(pixels)
        pixels_solid(pixels, COLOR_IDLE)
        thread.join()
        return ""

    # underlight cylon effect
    @app.route("/underlight")
    def underlight():
        thread = threading.Thread(target = lambda: play(sound_underlight), daemon = True)
        thread.start()
        pixels_cylon(pixels)
        pixels_solid(pixels, COLOR_IDLE)
        thread.join()
        return ""
    
    # meltdown effect
    @app.route("/meltdown")
    def meltdown():
        for count in range(4):
            thread = threading.Thread(target = lambda: play(sound_meltdown), daemon = True)
            thread.start()
            pixels_flash(pixels, (255,255,255), 2)
            pixels_flash(pixels, (255,0,0), 1)
            thread.join()
        pixels_solid(pixels, COLOR_IDLE)
        thread.join()
        return ""
    
    # lights-out
    @app.route("/lights-out")
    def lights_out():
        play(sound_lights_out)
        pixels_solid(pixels, (0,0,0))
        return ""
    
    @socketio.on('connect', namespace='/trajectory')
    def trajetory_connect():
        print("trajetory_connect()")
    
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    socketio.run(app,
                 host = "0.0.0.0",
                 port = 80,
                 allow_unsafe_werkzeug = True)

def speed_to_color(speed: float) -> list([float,float,float]):
    """
    Map a float value within the range [0, 1] to an RGB value.
    
    Parameters:
    speed (float): A float value between 0 and 1 inclusive.
    
    Returns:
    tuple: Corresponding RGB value as a tuple of integers (R, G, B).
    """
    # Ensure the input is within the range [0, 1]
    speed = max(min(speed, 1.0), 0.0)

    # Hue value for blue is around 0.66 and for red is 0.
    # We linearly interpolate between these two values based on the speed.
    hue = 0.66 * (1 - speed)
    saturation = 1     # Full saturation for pure color
    brightness = 0.5   # Brightness between [0,1]
    
    # Convert HSV to RGB
    float_rgb = colorsys.hsv_to_rgb(hue, saturation, brightness)
    # Map the RGB components to [0, 255]
    rgb = tuple(int(component * 255) for component in float_rgb)
    
    return rgb

def pixels_from_speed(timestamp: float, position: float, speed: float, pixels: neopixel.NeoPixel) -> None:
    speed = speed / ENCODER_PULSES_PER_REV
    color = None
    if speed > 0:
        # print("speed=" + str(speed) + " color=" + str(color))
        color = speed_to_color(speed)
        pixels_solid(pixels, color)

# global variables
telegraf_session = FuturesSession()
socketio = None

# application entrypoint
def main():
    rcode = 1

    try:
        print("Application starting")
        pixels = pixels_init()
        pixels_display_hello(pixels)
        pixels_solid(pixels)

        encoder = ScootEncoder(ENCODER_PIN, ENCODER_SMOOTHING, ENCODER_SPEED_ZERO_THRESHOLD_S)
        encoder.register_callback(telegraf_post_datapoint)
        encoder.register_callback(websocket_post_datapoint)
        encoder.register_callback(
            lambda timestamp, position, speed, pixels=pixels: pixels_from_speed(timestamp, position, speed, pixels))
        
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