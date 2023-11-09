#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo' as required by neopixel library.
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
from flask import Flask, render_template
from flask import send_from_directory  # send raw file
from flask_socketio import SocketIO, emit

# NeoPixel communication over GPIO 18 (pin 12)
PIXEL_PIN = board.D18
# NeoPixel total number of NeoPixels in the array
PIXEL_COUNT = 163
# NeoPixel idle color
PIXEL_COLOR_IDLE = (0, 0, 64)

# Encoder GPIO pin
ENCODER_PIN = 12  # GPIO 12 / pin 32
# Encoder counts per revolution of the wheel
ENCODER_PULSES_PER_REV = 4
# Encoder pulses per linear foot
# wheel diameter is 7.5", so circumference is pi * 7.5
ENCODER_PULSES_PER_FOOT = float(ENCODER_PULSES_PER_REV) / (math.pi * (7.5/12.0))
# Time since last encoder pulse after which the speed is assumed to be zero
ENCODER_SPEED_ZERO_THRESHOLD_S = 0.5
# Encoder speed smoothing coefficient (for exponential moving average)
ENCODER_SMOOTHING = 0.6

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

    def register_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register a callback to be issued upon every trajectory step.

        :param callback: method witih signature (timestamp: float, position: float, speed: float) -> None
        """
        self._step_callbacks.append(callback)
       

class ScootPixels:
    def __init__(self, pin, pixel_count):
        self._pin = pin
        self._pixel_count = pixel_count
        self._pixels = neopixel.NeoPixel(
            pin = self._pin,
            n = self._pixel_count,
            auto_write = False
        )

    def deinit(self):
        self._pixels.deinit()

    def tricolor(self):
        sequence = [(255,0,0), (0,255,0), (0,0,255)]
        for color in sequence:
            self.solid(color)
            time.sleep(0.250)
        self.solid()

    def underlight(self, count:int = 1):
        self.solid()

        # rotate cylon pattern
        for n in range(count):
            for color in [(1,0,0),(0,1,0),(0,0,1)]:
                # initial pattern
                for pixel in range(self._pixel_count):
                    value = int((1 - abs((self._pixel_count / 2) - pixel) / (self._pixel_count / 2)) * 255)
                    self._pixels[pixel] = tuple(value * k for k in color)

                for cycle in range(self._pixel_count):
                    last_pixel = self._pixels[0]
                    for pixel in range(self._pixel_count - 1):
                        self._pixels[pixel] = self._pixels[pixel + 1]
                    self._pixels[self._pixel_count-1] = last_pixel
                    self._pixels.show()
                    time.sleep(0.005)

                time.sleep(0.050) # give the CPU a break between colors

        self.solid()

    # display a colorful strobe pattern
    #   count:  number of strobes
    #   delay_s: time delay between flashes
    def disco(self, count:int = 10, delay_s: float = 0.0):
        for n in range(count):
            for color in [(255,0,0),(0,255,0),(0,0,255),(255,255,255)]:
                self.flash(color)
                if(delay_s > 0):
                    time.sleep(delay_s)

    # display a fill color that flashes on then off
    #   color:  color to display
    #   count:  number of flashes
    def flash(self, color:tuple = (255,255,255), count:int = 1):
        for n in range(count):
            self.solid()
            time.sleep(0.150)
            self.solid(color)
            # sleep if not last flash
            if n + 1 < count:
                time.sleep(0.150)

    # display a solid color
    #   color:  color to display
    def solid(self, color: tuple = (0,0,0)):
        self._pixels.fill(color)
        self._pixels.show()


class ScootEncoder:
    # encoder init
    def __init__(self,
                 encoder_pin: board.pin,
                 alpha: float = 0.5,
                 zero_speed_threshold_s = 0.5):
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

# application entrypoint
if __name__ == '__main__':
    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    socketio = SocketIO(app, cors_allowed_origins = "*")

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
        thread = threading.Thread(target = lambda: play(sound_disco))
        thread.start()
        pixels.disco(2, 0.5)
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        return ""

    # underlight cylon effect
    @app.route("/underlight")
    def underlight():
        thread = threading.Thread(target = lambda: play(sound_underlight))
        thread.start()
        pixels.underlight()
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        return ""

    # meltdown effect
    @app.route("/meltdown")
    def meltdown():
        for count in range(3):
            thread = threading.Thread(target = lambda: play(sound_meltdown))
            thread.start()
            pixels.flash((255,255,255), 2)
            pixels.flash((255,0,0), 1)
            thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        return ""

    # lights-out
    @app.route("/lights-out")
    def lights_out():
        thread = threading.Thread(target = lambda: play(sound_lights_out))
        thread.start()
        thread.join()
        pixels.solid()
        return ""
    
    @socketio.on('connect', namespace='/trajectory')
    def trajetory_connect():
        print("websocket connect: /trajectory")
    
    print("Initializing pixels")
    pixels = ScootPixels(PIXEL_PIN, PIXEL_COUNT)
    pixels.tricolor()
    pixels.solid(PIXEL_COLOR_IDLE)
    print("... pixels initialized")

    encoder = ScootEncoder(ENCODER_PIN, ENCODER_SMOOTHING, ENCODER_SPEED_ZERO_THRESHOLD_S)
    encoder.register_callback(lambda timestamp, position, speed, socketio = socketio : 
        socketio.emit('newdata', {
            'timestamp': math.ceil(timestamp * 1000),
            'position': position,
            'speed': speed },
        namespace='/trajectory')
    )

    # import sounds
    # the time window of acoustic interest is determined emprically, in ms
    print("importing sounds")
    sound_meltdown = AudioSegment.from_mp3("static/sounds/meltdown.mp3")[100:1250]
    sound_disco = AudioSegment.from_mp3("static/sounds/disco.mp3")[5000:9500]
    sound_underlight = AudioSegment.from_mp3("static/sounds/underlight.mp3")[250:6000]
    sound_lights_out = AudioSegment.from_mp3("static/sounds/lights-out.mp3")[4900:6250]
    print("... sounds imported")
    
    socketio.run(app,
                 host = "0.0.0.0",
                 port = 80,
                 allow_unsafe_werkzeug = True)
    
    pixels.solid((0,0,0))
    pixels.deinit()
    GPIO.cleanup()

    print("Application exiting")
    sys.exit(0)