# Pimp my Gimp

>_When Life Gives You Lemons, You Paint That Shit Gold_
> <br>\- Atmosphere

Pimp out your mobility knee scoter! Trick out your scooter with battery-operated programmable LED underlighting, speakers and real-time speedometer. Powered by Raspberry Pi and Python.

<img src="https://i.imgur.com/owE0TVs.jpg"
    height="250"
    width="250"
    alt="x-ray of pin implanted in a broken ankle"/>
&nbsp;
<img src="https://m.media-amazon.com/images/I/81JP777YLmL._AC_SL1500_.jpg"
    height="250"
    width="250"
    alt="hot pink knee scooter"/>

# Features
Base features:
- Programmable LED underlighting
- Mobile-friendly web interface
- Battery operated

Additional optional features:
- Audio output
- Odometer, speedometer & speed-responsive lights

# How to Use

## Install prerequisites

Install docker on your Raspberry Pi:
```shell
sudo apt update -q
sudo apt install -y software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-add-repository -y "deb https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod ${USER} -aG docker
```


## Run pimp-my-gimp

```shell
docker run --name pimp-my-gimp --privileged -p 80:80/tcp elgeeko/pimp-my-gimp
```


# Hardware Materials

### Scooter, Raspberry Pi, battery & LED strip light
- Scooter
  - [KneeRover Knee Scooter](https://www.amazon.com/dp/B01J4AMXD8)
- Raspberry Pi
  - [Raspberry Pi 4B](https://www.raspberrypi.com/products/raspberry-pi-4-model-b/)
  - [Samsung PRO Endurance 32GB MicroSDXC Memory Card](https://www.amazon.com/gp/product/B09W9XYQCQ)
  - [Miuzei Raspberry Pi 4B Case](https://www.amazon.com/dp/B0C1NJP77D)
- LED strip light
  - [Adafruit NeoPixel 332 LED-per-Meter Silicone Bead LED Strip](https://www.adafruit.com/product/4865)
- Power
  - [Talentcell 22400mAh 82.88Wh lithium ion battery PB240A1](https://www.amazon.com/dp/B078T7M9HZ)
  - [ALITOVE 5V 10A Power Supply](https://www.amazon.com/dp/B0852HL336) (for prototyping)
- Wiring
  - [USB 2.0 Male Bare Cable Pigtail](https://www.amazon.com/dp/B09ZQNJ2DJ)
  - [3-pin JST SM Plug](https://www.adafruit.com/product/1663)

### Speakers
- DAC
  - [Cubilux USB to 3.5mm Audio Adapter](https://a.co/d/5YjWS0N)
- Amplifier
  - [SparkFun Qwiic Speaker Amp](https://www.sparkfun.com/products/20690)
- Speakers
  - [Sparkfun Thin Speaker - 4 Ohm, 2.5W, 28mm](https://www.sparkfun.com/products/21311)
- Wiring
  - [3.5mm Audio Cable - Male to Male](https://www.amazon.com/3-5mm-CGTime-Plated-Auxiliary-Stereo/dp/B074QHNY5Q)


# References

### Software
- [Adafruit NeoPixel UberGuide](https://learn.adafruit.com/adafruit-neopixel-uberguide)
- [Adafruit CircuitPython NeoPixel library](https://github.com/adafruit/Adafruit_CircuitPython_NeoPixel)

### Tutorials
- [The raspi-config tool](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [Manage your Raspberry Pi fleet with Ansible](https://opensource.com/article/20/9/raspberry-pi-ansible)
- [Installing Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html)

# Authors

- [elgeeko1](https://www.raspberrypi.com/documentation/computers/configuration.html)
- [slkollasch](https://github.com/slkollasch)