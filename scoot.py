import time
import board
import neopixel

PIXEL_COUNT = 165

pixels = neopixel.NeoPixel(
    board.D18,
    PIXEL_COUNT
)

pixels.fill((255,0,0))
time.sleep(1)
pixels.fill((0,255,0))
time.sleep(1)
pixels.fill((0,0,255))
time.sleep(1)
pixels.fill((0,0,0))
time.sleep(1)


pixels.fill((0,0,0))
for pixel in range(PIXEL_COUNT):
    color = int((1 - abs((PIXEL_COUNT / 2) - pixel) / (PIXEL_COUNT / 2)) * 255)
    pixels[pixel] = (color,0,0)
    time.sleep(0.001)
    print("pixels[" + str(pixel) + "] = " + str(color))
time.sleep(10)
pixels.fill((0,0,0))


