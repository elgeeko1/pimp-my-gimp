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
import sys
import os
import math
from typing import Callable

# NeoPixels
import scootpixels

# Audio effects
import scootsound

# Odometer
import scootodometer

# Detect if running on a Raspberry Pi
import raspi_detect

# IO
if raspi_detect.is_raspi:
    import board
else:
    class board:
        pin = int
        D18: pin = 0

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
ENCODER_PULSES_PER_REV = 8
# Encoder pulses per linear foot
# wheel diameter is 7.5", so circumference is pi * 7.5
ENCODER_PULSES_PER_FOOT = float(ENCODER_PULSES_PER_REV) / (math.pi * (7.5/12.0))
# Time since last encoder pulse after which the speed is assumed to be zero
ENCODER_SPEED_ZERO_THRESHOLD_S = 1
# Encoder speed smoothing coefficient (for exponential moving average)
ENCODER_SMOOTHING = 0.75

# Program cache directory for persistent data
CACHE_DIR = "cache/"


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
        "--no-odometer",
        action="store_true",
        help="disable odometer")
    parser.add_argument(
        "--no-light",
        action="store_true",
        help="disable LED output")
    args = parser.parse_args()
    audio_enabled = True
    if args.no_audio:
        print("Audio output disabled")
        audio_enabled = False
    odometer_enabled = True
    if args.no_odometer:
        odometer_enabled = False
        print("Odometer disabled")
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

    @app.route("/fireplace")
    def fireplace():
        """
        Handle the fireplace effect route.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/fireplace': Accessed by {request.remote_addr}")
        thread = sounds.play(sounds.sound_fireplace)
        pixels.fireplace()
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        print("... Endpoint '/fireplace' complete")
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

    @app.route("/energyweapon")
    def energyweapon():
        """
        Handle the energyweaspon effect route.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/energyweapon': Accessed by {request.remote_addr}")
        thread = sounds.play(sounds.sound_energyweapon)
        pixels.energyweapon()
        thread.join()
        pixels.solid(PIXEL_COLOR_IDLE)
        print("... Endpoint '/energyweapon' complete")
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
    
    @app.route("/color")
    def color():
        """
        Handle the color route to set pixels to a user-specified color.
        
        :return: An empty string response after the effect.
        """
        print(f"Endpoint '/color': Accessed by {request.remote_addr}")
        idle_color = "#{:02x}{:02x}{:02x}".format(*PIXEL_COLOR_IDLE)
        hex_color = request.args.get('rgb', default=idle_color, type=str)
        # Check if the hex color starts with '#', and remove it
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]

        # Check if the remaining string has a length of 6
        if len(hex_color) != 6:
            print("Error: Invalid hex color length. Must be 6 characters long.")
            return
        # Check if all characters are valid hexadecimal digits
        if not all(c in '0123456789abcdefABCDEF' for c in hex_color):
            print("Error: Invalid hex color. Contains non-hexadecimal characters.")

        print("Color selected: " + hex_color)

        # Convert the characters from hex to integers
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        pixels.solid((r,g,b))

        print("... Endpoint '/color' complete")
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

    print("Reading odometer cache.")
    odometer_cache = scootodometer.ScootOdometerCache(CACHE_DIR + "odometer.ini")
    print("... read last known position " + str(odometer_cache.get_distance()))

    print("Initializing pixels")
    pixels = scootpixels.ScootPixels(PIXEL_PIN, PIXEL_COUNT, pixels_enabled)
    pixels.tricolor()
    pixels.solid(PIXEL_COLOR_IDLE)
    print("... pixels initialized")

    print("Initializing odometer")
    odometer = scootodometer.ScootOdometer(ENCODER_PIN,
                                           ENCODER_SMOOTHING,
                                           ENCODER_SPEED_ZERO_THRESHOLD_S,
                                           odometer_cache.get_distance(),
                                           odometer_enabled)
    # WebSocket emit on encoder pulses
    odometer.register_callback(lambda timestamp, position, speed, socketio = socketio : 
        socketio.emit('newdata', {
            'timestamp': math.ceil(timestamp * 1000),
            'position': position / ENCODER_PULSES_PER_FOOT,
            'speed': speed / ENCODER_PULSES_PER_FOOT},
        namespace='/trajectory')
    )
    # Update persistent data on encoder pulses
    odometer.register_callback(lambda timestamp, position, speed, odometer_cache = odometer_cache:
        # Write cache every 100 pulses
        (position - odometer_cache.get_distance() > 100) and odometer_cache.set_distance(timestamp, position, speed) 
    )
    print("... odometer initialized")

    print("Initializing sounds")
    sounds = scootsound.ScootSound(audio_enabled)
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
        odometer.deinit()
        odometer_cache.deinit()
        pixels.solid()
        pixels.deinit()

    print("Application terminated")
    sys.exit(0)