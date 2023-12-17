import raspi_detect

if raspi_detect.is_raspi:
    import neopixel

import time
import random

class ScootPixels:
    """
    A class to manage the NeoPixel LED on a scooter, allowing for various lighting effects
    such as tricolor sequence, underlight cylon pattern, disco strobe, and solid color display.

    Attributes:
        _pin: GPIO identifier to which the NeoPixel LEDs are connected.
        _pixel_count: The total number of NeoPixel LEDs.
        _pixels: Instance of NeoPixel class to control the LEDs.
    """

    def __init__(self, pin, pixel_count: int, enabled: bool = raspi_detect.is_raspi):
        """
        Initialize the ScootPixels with the specified pin and pixel count.

        :param pin: The GPIO pin where the NeoPixel LEDs are connected, i.e. 18 = GPIO 18 (pin 12).
        :param pixel_count: The number of NeoPixel LEDs.
        :param enabled: Enable hardware output.
        """
        self._pin = pin
        self._pixel_count = pixel_count
        self.enabled = enabled

        if not raspi_detect.is_raspi:
            self.enabled = False
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

    def fireplace(self, duration_s = 5.0):
        """
        Show a fireplace.

        :param duration: The duration of the fireplace effect.
        """
        if not self.enabled:
            return

        # alpha, brightnesss
        brightness = 0.25
        start_time = time.time()
        last_color = [(0.0, 0.0, 0.0)] * self._pixel_count
        while time.time() - start_time < duration_s:
            for pixel in range(self._pixel_count):
                last_r, last_g, last_b = last_color[pixel]
                # randomly choose colors within the range of fire colors
                r = int(min(255, max(0, last_r + random.randint(-255, 255))) * brightness)
                g = int(min(96, max(0, last_g + random.randint(-6, 6))) * brightness)
                b = int(min(48, max(0, last_b + random.randint(-4, 4))) * brightness)
                self._pixels[pixel] = tuple([r, g, b])
                last_color[pixel] = (r, g, b)
            self._pixels.show()
            time.sleep(0.125)

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

    def energyweapon(self):
        """
        Display an energy weapon pattern, with a chargeup and blast.
        """
        if not self.enabled:
            return
        
        self.off()
        
        # Fill green one LED at a time
        for pixel in range(self._pixel_count):
            self._pixels[pixel] = (0, 255, 0)
            self._pixels.show()
            time.sleep(2.5 / self._pixel_count)  # two second duration

        # Fade to white
        num_steps = 10
        for step in range(num_steps):
            color = (step * 255 // num_steps, 255, step * 255 // num_steps)
            for pixel in range(self._pixel_count):
                self._pixels[pixel] = color
            self._pixels.show()
            time.sleep(0.75 / num_steps)

        # Change to red, two at a time
        for pixel in range(0, self._pixel_count, 2):
            self._pixels[pixel] = (255, 0, 0)  # Red color
            if pixel + 1 < self._pixel_count:
                self._pixels[pixel + 1] = (255, 0, 0)
            self._pixels.show()

        # Fade to black
        num_steps = 100
        for step in range(num_steps, -1, -1):
            color = (step * 255 // num_steps, 0, 0)
            for pixel in range(self._pixel_count):
                self._pixels[pixel] = color
            self._pixels.show()
            time.sleep(2.0 / num_steps)
                
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