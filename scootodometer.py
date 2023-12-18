import time
import threading
from typing import Callable
import atexit

import sys
import os
from configparser import ConfigParser

# IO libraries
import raspi_detect
if raspi_detect.is_raspi:
    import RPi.GPIO as GPIO
    import board
else:
    class board:
        pin = int

import math

class ScootOdometer:
    """
    A class responsible for handling encoder signals for a scooter, managing speed detection
    and trajectory calculations.

    Attributes:
        _trajectory (Trajectory): An instance of Trajectory used to record the movement.
        _zero_speed_threshold_s (float): The threshold in seconds to determine if the scooter is at zero speed.
    """

    def __init__(self,
                 encoder_pin: board.pin,
                 alpha: float = 0.75,
                 zero_speed_threshold_s: float = 0.75,
                 initial_position: float = 0.0,
                 enabled: bool = raspi_detect.is_raspi):
        """
        Initialize the encoder with a pin, alpha value for trajectory smoothing, and zero speed threshold.

        :param encoder_pin: The GPIO pin number connected to the encoder.
        :param alpha: The alpha value used for trajectory smoothing. Defaults to 0.75.
        :param zero_speed_threshold_s: The time threshold in seconds to consider the scooter to be at zero speed. Defaults to 0.75.
        :param initial_position: The initial position of the encoder, in pulses.
        :param enabled: Enable the hardware peripheral.
        """
        self._trajectory = Trajectory(alpha, initial_position)
        self._zero_speed_threshold_s = zero_speed_threshold_s
        self.enabled = enabled
        self._encoder_check_speed_thread = threading.Thread(target = lambda: None)

        if not raspi_detect.is_raspi:
            self.enabled = False

        if self.enabled:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(encoder_pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(encoder_pin, GPIO.RISING, callback = self.encoder_handler)

            # Start a daemon thread to check the speed periodically and adjust the trajectory.
            self._encoder_check_speed_thread = threading.Thread(target = self.encoder_check_speed, daemon = True)
            self._encoder_check_speed_thread.start()

    def deinit(self):
        """
        De-initialize the encoder with a pin. Terminates speed check thread and cleans up GPIO pins.
        """
        if self.enabled:
            self.enabled = False  # signals encoder thread to stop
            self._encoder_check_speed_thread.join()
            GPIO.cleanup()

    def encoder_handler(self, channel: int):
        """
        Handle the encoder edge event callback. Called automatically in a separate thread on encoder pulses.

        :param channel: The GPIO channel that triggered the event.
        """
        self._trajectory.step(1.0)

    def encoder_check_speed(self):
        """
        Execute periodically to determine if the speed is zero and add zero points to the trajectory.
        """
        while self.enabled:
            timestamp, _ = self._trajectory.speed()
            # Check if the current time exceeds the threshold since the last pulse.
            if time.time() - timestamp > self._zero_speed_threshold_s:
                self._trajectory.not_moving()
            time.sleep(self._zero_speed_threshold_s / 2)

    def register_callback(self, callback: Callable[[float, float, float], None]):
        """
        Register a callback to be called upon every trajectory step.

        :param callback: The callback method with the signature (timestamp: float, position: float, speed: float) -> None
                         that will be called with trajectory information.
        """
        self._trajectory.register_callback(callback)


class ScootOdometerCache:
    """
    Persists the most recent values for a scooter odometer to an INI file.
    It maintains 'distance_pulses' as a floating-point number and 'timestamp', updating them through a method.
    """

    def __init__(self, filename: str = "odometer.ini", write_interval_s: int = 60):
        """
        Initializes the ScootOdometerCache object with the provided filename and write interval.

        :param filename: The name of the file to which the most recent odometer values will be persisted.
                         Defaults to "odometer.ini".
        :param write_interval_s: The interval, in seconds, at which the most recent values are written to the file.
                                 Defaults to 60 seconds.
        """
        self.filename = filename
        self.config = ConfigParser()
        self.distance_pulses = 0.0 
        self.timestamp = 0.0 
        self.write_interval_s = write_interval_s
        self._cache_read()
        self._cache_write_timer_init()
        atexit.register(self.deinit)

    def _cache_read(self):
        """
        Loads the most recent values from the cache or initializes the cache with default values.
        """
        try:
            if not os.path.exists(self.filename):
                self.config['DEFAULT'] = {
                    'distance_pulses': str(self.distance_pulses),
                    'timestamp': str(self.timestamp)
                }
                self._cache_write()
            else:
                self.config.read(self.filename)
                self.distance_pulses = float(self.config['DEFAULT'].get('distance_pulses', 0.0))
                self.timestamp = float(self.config['DEFAULT'].get('timestamp', 0.0))
        except Exception as e:
            sys.stderr.write(f"Error loading most recent values: {e}\n")

    def _cache_write(self):
        """
        Writes the most recent values of 'distance_pulses' and 'timestamp' to the cache.
        """
        try:
            self.config['DEFAULT']['distance_pulses'] = str(self.distance_pulses)
            self.config['DEFAULT']['timestamp'] = str(self.timestamp)
            with open(self.filename, 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            sys.stderr.write(f"Error writing most recent values: {e}\n")

    def _cache_write_timer_init(self):
        """
        Initializes the timer to periodically write the most recent values to the cache.
        """
        self.timer = threading.Timer(self.write_interval_s, self._cache_write)
        self.timer.daemon = True  # Make the timer thread a daemon thread
        self.timer.start()

    def set_distance(self, timestamp: float, distance: float, speed: float):
        """
        Sets the most recent value of 'distance_pulses' and updates the 'timestamp'. The 'speed' parameter is accepted
        for API compatibility but is currently unused.

        :param timestamp: The current timestamp as a float representing seconds since the epoch.
        :param distance: The new most recent value to set for 'distance_pulses', representing the number of encoder pulses.
        :param speed: The speed in pulses per second.
        """
        self.distance_pulses = distance
        self.timestamp = timestamp

    def get_distance(self) -> float:
        """
        Retrieves the most recent value of 'distance_pulses'.

        :return: The current 'distance_pulses' value as a float.
        """
        return self.distance_pulses

    def deinit(self):
        """
        Stops the timer and writes the most recent values one last time before exiting.
        """
        self.timer.cancel()
        self._cache_write()


class Trajectory:
    """
    The Trajectory class calculates and stores the position and speed of an object over time.
    Exponential smoothing is applied to speed data to reduce noise and variability in the measurements.
    """

    def __init__(self, alpha: float = 0.75, initial_position = 0.0):
        """
        Initializes the Trajectory with a specified window size for the buffers and a smoothing factor for speed calculation.

        :param alpha: The smoothing factor used for exponential smoothing of the speed data.
        :param initial_position: The initial position of the encoder, in pulses.
        """
        self._last_timestamp = time.time()  # Stores the timestamp of the last update
        self._last_position = initial_position  # Stores the last calculated position
        self._last_speed = 0.0  # Stores the last calculated speed
        self._speed_filter = ExponentialSmoothing(alpha, 0.001)  # Exponential smoothing filter for speed
        self._step_callbacks = []
        
    def step(self, step_pulses: float = 1.0):
        """
        Updates the position and speed based on the step pulses received since the last update.

        :param step_pulses: The number of pulses since the last update, which is proportional to the distance moved.
        """
        timestamp = time.time()
        dt = timestamp - self._last_timestamp
        new_position = self._last_position + step_pulses
        new_speed = self._speed_filter.smooth(step_pulses / dt)
        self._last_timestamp = timestamp
        self._last_position = new_position
        self._last_speed = new_speed

        # issue callbacks
        for callback in self._step_callbacks:
            callback(timestamp, new_position, new_speed)

    def not_moving(self):
        """
        Update trajectory to indicate no movement. Use to produce timedstamped outputs even with no speed.
        """
        current_time = time.time()
        # issue callbacks
        for callback in self._step_callbacks:
            callback(current_time, self._last_position, 0.0)

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


class ExponentialSmoothing:
    """
    Exponential smoothing algorithm for time series data.
    """
    def __init__(self, alpha: float = 0.75, zero_tolerance = -math.inf):
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