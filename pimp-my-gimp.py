#!/usr/bin/env python

#########
# Pimp my Gimp application
# 
# May be run standalone or as a system service.
# Must be run as 'sudo' as required by neopixel library.
#########

# threading
from gevent import monkey
monkey.patch_all()
import threading

# system libraries
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
# be sure to import threading libraries prior to these imports
# as the subprocess behavior will be different
from pydub import AudioSegment
from pydub.playback import play

# webserver libraries
from flask import Flask, render_template
from flask import send_from_directory  # send raw file
from flask import request
from flask_socketio import SocketIO, emit

# argument parser
import argparse

# NeoPixel communication pin 
PIXEL_PIN = board.D18  # GPIO 18 / pin 12
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
       

class ScootEncoder:
    """
    A class responsible for handling encoder signals for a scooter, managing speed detection
    and trajectory calculations.

    Attributes:
        _trajectory (Trajectory): An instance of Trajectory used to record the movement.
        _zero_speed_threshold_s (float): The threshold in seconds to determine if the scooter is at zero speed.
    """

    def __init__(self,
                 encoder_pin: board.pin,
                 alpha: float = 0.5,
                 zero_speed_threshold_s: float = 0.5,
                 enabled: bool = True):
        """
        Initialize the encoder with a pin, alpha value for trajectory smoothing, and zero speed threshold.

        :param encoder_pin: The GPIO pin number connected to the encoder.
        :param alpha: The alpha value used for trajectory smoothing. Defaults to 0.5.
        :param zero_speed_threshold_s: The time threshold in seconds to consider the scooter to be at zero speed. Defaults to 0.5.
        :param enabled: Enable the hardware peripheral.
        """
        self._trajectory = Trajectory(alpha)
        self._zero_speed_threshold_s = zero_speed_threshold_s
        self.enabled = enabled

        if self.enabled:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(encoder_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(encoder_pin, GPIO.RISING, callback = self.encoder_handler)

            # Start a daemon thread to check the speed periodically and adjust the trajectory.
            encoder_check_speed_thread = threading.Thread(target = self.encoder_check_speed, daemon = True)
            encoder_check_speed_thread.start()

    def encoder_handler(self, channel: int):
        """
        Handle the encoder edge event callback. Called automatically in a separate thread on encoder pulses.

        :param channel: The GPIO channel that triggered the event.
        """
        self._trajectory.step(1.0)

    def encoder_check_speed(self):
        """
        Execute periodically to determine if the speed is zero and add zero points to the trajectory.
        Introduces a latency of half the zero_speed_threshold_s to account for encoder pulses that may arrive
        soon after the execution of this method, preventing artificially inflated speeds.
        """
        while True:
            timestamp, _ = self._trajectory.speed()
            # Check if the current time exceeds the threshold since the last pulse.
            if time.time() - timestamp > self._zero_speed_threshold_s:
                self._trajectory.step(0.0, -self._zero_speed_threshold_s)
            time.sleep(self._zero_speed_threshold_s / 2)

    def register_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register a callback to be called upon every trajectory step.

        :param callback: The callback method with the signature (timestamp: float, position: float, speed: float) -> None
                         that will be called with trajectory information.
        """
        self._trajectory.register_callback(callback)


class ScootPixels:
    """
    A class to manage the LED pixels on a scooter, allowing for various lighting effects
    such as tricolor sequence, underlight cylon pattern, disco strobe, and solid color display.

    Attributes:
        _pin: Pin to which the NeoPixel LEDs are connected.
        _pixel_count: The total number of NeoPixel LEDs.
        _pixels: Instance of NeoPixel class to control the LEDs.
    """

    def __init__(self, pin, pixel_count: int, enabled: bool = True):
        """
        Initialize the ScootPixels with the specified pin and pixel count.

        :param pin: The pin where the NeoPixel LEDs are connected.
        :param pixel_count: The number of NeoPixel LEDs.
        :param enabled: Enable hardware output.
        """
        self._pin = pin
        self._pixel_count = pixel_count
        self.enabled = enabled

        if self.enabled:
            self._pixels = neopixel.NeoPixel(
                pin = self._pin,
                n = self._pixel_count,
                auto_write = False
            )
            self.off()

    def deinit(self):
        """
        Deinitialize the pixels and release the resources.
        """
        if not self.enabled:
            return
        self.off()
        self._pixels.deinit()

    def tricolor(self):
        """
        Display a tricolor sequence on the LEDs, cycling through red, green, and blue.
        """
        if not self.enabled:
            return
        sequence = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
        for color in sequence:
            self.solid(color)
            time.sleep(0.250)
        self.off()  # Turn off the lights after the sequence

    def underlight(self, count: int = 1):
        """
        Display a 'cylon' pattern underneath the scooter, moving back and forth.

        :param count: The number of times to repeat the cylon pattern.
        """
        if not self.enabled:
            return
        # Rotate the cylon pattern for the specified count
        for n in range(count):
            for color in [(1, 0, 0), (0, 1, 0), (0, 0, 1)]:
                # Initialize pattern
                for pixel in range(self._pixel_count):
                    value = int((1 - abs((self._pixel_count / 2) - pixel) / (self._pixel_count / 2)) * 255)
                    self._pixels[pixel] = tuple(value * k for k in color)

                # Cycle the pattern through the pixels
                for cycle in range(self._pixel_count):
                    last_pixel = self._pixels[0]
                    for pixel in range(self._pixel_count - 1):
                        self._pixels[pixel] = self._pixels[pixel + 1]
                    self._pixels[self._pixel_count - 1] = last_pixel
                    self._pixels.show()
                    time.sleep(0.005)

                time.sleep(0.050)  # Give the CPU a break between colors

        self.off()  # Turn off the lights after the pattern

    def disco(self, count: int = 10, delay_s: float = 0.1):
        """
        Display a colorful strobe pattern resembling a disco light.

        :param count: The number of strobe flashes.
        :param delay_s: The time delay in seconds between each flash.
        """
        if not self.enabled:
            return
        for n in range(count):
            for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255)]:
                self.flash(color)
                if delay_s > 0:
                    time.sleep(delay_s)

    def flash(self, color: tuple = (255, 255, 255), count: int = 1):
        """
        Display a color that flashes on and then off.

        :param color: The color to flash.
        :param count: The number of times to flash the color.
        """
        if not self.enabled:
            return
        for n in range(count):
            self.off()  # Turn off before flashing
            time.sleep(0.150)
            self.solid(color)
            if n + 1 < count:  # Sleep if not the last flash
                time.sleep(0.150)

    def solid(self, color: tuple = (0, 0, 0)):
        """
        Display a solid color across all LEDs.

        :param color: The color to display.
        """
        if not self.enabled:
            return
        self._pixels.fill(color)
        self._pixels.show()

    def off(self):
        """
        Turn off all LEDS.
        """
        if not self.enabled:
            return
        self.solid((0, 0, 0))


class ScootSound:
    """
    Class to manage and play different audio effects for the scooter.

    Attributes:
        sound_meltdown (AudioSegment): An audio segment for the 'meltdown' mode.
        sound_disco (AudioSegment): An audio segment for the 'disco' mode.
        sound_underlight (AudioSegment): An audio segment for the 'underlight' mode.
        sound_lights_out (AudioSegment): An audio segment for the 'lights out' mode.

    Depencencies:
        threading
        pydub

    :param enabled: bool: Enable audio output.
    """
    def __init__(self, enabled: bool = True):
        """
        Initializes the ScootSound class with empty audio segments.
        """
        self.enabled = enabled
        self.sound_meltdown = AudioSegment.empty()
        self.sound_disco = AudioSegment.empty()
        self.sound_underlight = AudioSegment.empty()
        self.sound_lights_out = AudioSegment.empty()

    def import_from_disk(self):
        """
        Imports audio files from the disk into their corresponding attributes.
        Assumes the existence of MP3 files in the 'static/sounds/' directory.
        This method blocks while reading and parsing audio, which may be lengthy.
        """
        if self.enabled:
            self.sound_meltdown = AudioSegment.from_mp3("static/sounds/meltdown.mp3")
            self.sound_disco = AudioSegment.from_mp3("static/sounds/disco.mp3")
            self.sound_underlight = AudioSegment.from_mp3("static/sounds/underlight.mp3")
            self.sound_lights_out = AudioSegment.from_mp3("static/sounds/lights-out.mp3")

    def play(self, segment: AudioSegment) -> threading.Thread:
        """
        Plays an audio segment in a new daemon thread.

        :param segment (AudioSegment): The audio segment to be played.
        :return threading.Thread: The thread in which the audio segment is being played.
        """
        thread = threading.Thread()
        if self.enabled:
            thread = threading.Thread(target = lambda: play(segment), daemon = True)
        else:
            thread = threading.Thread(target = lambda: None)
        thread.start()
        return thread


# application entrypoint
if __name__ == '__main__':
    # parse arguments
    parser = argparse.ArgumentParser(
        prog='pimp-my-gimp.py',
        description='Webserver and controller for enhanced mobility devices.',
        epilog='May your journey be illuminated.')
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="disable audio output")
    parser.add_argument(
        "--no-speed",
        action="store_true",
        help="disable speed encoder")
    parser.add_argument(
        "--no-light",
        action="store_true",
        help="disable LED output")
    args = parser.parse_args()
    audio_enabled = True
    if args.no_audio:
        print("Audio output disabled")
        audio_enabled = False
    encoder_enabled = True
    if args.no_speed:
        encoder_enabled = False
        print("Speedometer disabled")
    pixels_enabled = True
    if args.no_light:
        pixels_enabled = False
        print("Light disabled")

    # Initialize Flask app and SocketIO
    app = Flask(__name__)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    socketio = SocketIO(app, cors_allowed_origins = "*", async_mode = "gevent")

    @app.route("/")
    def index():
        """
        Serve the index page.
        
        :return: Rendered index.html template.
        """
        print(f"Endpoint '/': Accessed by {request.remote_addr}")
        return render_template('index.html')

    @app.route("/favicon.ico")
    def favicon():
        """
        Serve the favicon.ico file.
        
        :return: favicon.ico from the static/images directory.
        """
        print(f"Endpoint '/favicon.ico': Accessed by {request.remote_addr}")
        return send_from_directory(
            os.path.join(app.root_path, 'static/images'),
            'favicon.ico',
            mimetype='image/vnd.microsoft.icon')

    @app.route("/manifest.json")
    def manifest():
        """
        Serve the manifest.json file.
        
        :return: manifest.json from the static directory.
        """
        print(f"Endpoint '/manifest.json': Accessed by {request.remote_addr}")
        return send_from_directory(
            os.path.join(app.root_path, 'static'),
            'manifest.json',)

    @app.route("/disco")
    def disco():
        """
        Handle the disco route to initiate a disco effect with sound and lights.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/disco': Accessed by {request.remote_addr}")
        thread = sounds.play(sounds.sound_disco)
        pixels.disco(2, 0.5)
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        print("... Endpoint '/disco' complete")
        return ""

    @app.route("/underlight")
    def underlight():
        """
        Handle the underlight route to start the underlight effect.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/underlight': Accessed by {request.remote_addr}")
        thread = sounds.play(sounds.sound_underlight)
        pixels.underlight()
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        print("... Endpoint '/underlight' complete")
        return ""

    @app.route("/meltdown")
    def meltdown():
        """
        Handle the meltdown route to perform the meltdown effect with flashing lights.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/meltdown': Accessed by {request.remote_addr}")
        for count in range(3):
            thread = sounds.play(sounds.sound_meltdown)
            pixels.flash((255,255,255), 2)
            pixels.flash((255,0,0), 1)
            thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        print("... Endpoint '/meltdown' complete")
        return ""

    @app.route("/lights-out")
    def lights_out():
        """
        Handle the lights-out route to turn off all lights.
        
        :return: An empty string response after turning off the lights.
        """
        print(f"Endpoint '/lights-out': Accessed by {request.remote_addr}")
        sounds.play(sounds.sound_lights_out).join()
        pixels.off()
        print("... Endpoint '/lights-out' complete")
        return ""
        
    @socketio.on('connect', namespace='/trajectory')
    def trajectory_connect():
        """
        Handle websocket connection for the /trajectory namespace.
        
        Logs the IP address of the client that made the connection.

        :return: None.
        """
        client_ip = request.remote_addr  # Gets the client's IP address
        print(f"WebSocket client connected from {client_ip}: /trajectory")

    print("Initializing pixels")
    pixels = ScootPixels(PIXEL_PIN, PIXEL_COUNT, pixels_enabled)
    pixels.tricolor()
    pixels.solid(PIXEL_COLOR_IDLE)
    print("... pixels initialized")

    print("Initializing encoder")
    encoder = ScootEncoder(ENCODER_PIN,
                           ENCODER_SMOOTHING,
                           ENCODER_SPEED_ZERO_THRESHOLD_S,
                           encoder_enabled)
    encoder.register_callback(lambda timestamp, position, speed, socketio = socketio : 
        socketio.emit('newdata', {
            'timestamp': math.ceil(timestamp * 1000),
            'position': position,
            'speed': speed },
        namespace='/trajectory')
    )
    print("... encoder initialized")

    print("Initializing sounds")
    sounds = ScootSound(audio_enabled)
    sounds.import_from_disk()
    print("... sounds initialized")
    
    try:
        print("Starting Flask server")
        socketio.run(app,
                    host = "0.0.0.0",
                    port = 80)
    except KeyboardInterrupt:
        print("Flask server terminated.")
    finally:
        pixels.deinit()
        GPIO.cleanup()

    print("Application terminated")
    sys.exit(0)