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
- Odometer / speedometer

# System Diagram



# Flash Ubuntu Server to your SD card
Follow the guide [How to install Ubuntu Server on your Raspberry Pi](https://ubuntu.com/tutorials/how-to-install-ubuntu-on-your-raspberry-pi#1-overview) to flash Ubuntu Server to your SD card.

In step 3 "Advanced options" set the following username and password:
> username: ubuntu <br>
password: [a password you'll remember]

You may skip step 5 "Install a Desktop".

Take note of the IP address of the device once it is online.

# Install pimp-my-gimp
There are two methods to configure the Raspberry Pi operating system with the packages
needed to run the application.

*Install on-target*: Use SSH and run commands directly on the device. This is the most
straightforward method.

*Use Ansible from a host controller* (advanced): Use the Ansible provisioning tool on your
host computer to remotely provision the Rasberry Pi. This requires installing the Ansible
toolchain 
and some familiarity with the tool.

Once installed, a webserver will be running on port 80 of your device.

### Install method 1: Configure on-target (easiest)

First confirm you are able to connect to the target via SSH. Then copy the contents of this github repository
to the target (replacing the IP address with that 
of your raspberry pi):
```console
scp -r pimp-my-gimp ubuntu@192.168.1.100:
```

Run the remainder of these commands from an SSH
terminal on your Raspberry Pi (`ssh ubuntu@192.168.1.100` -- replace the IP address with that of your
device.)
 
```console
sudo apt update

sudo apt install python3-pip sshpass

pip install --user ansible
```

Add Ansible to the path and confirm execution
by checking the Ansible version.

```console
echo 'PATH="$PATH:/home/ubuntu/.local/bin"' >> ~/.bashrc

source ~/.bashrc

ansible --version
```

Change into the pimp-my-gimp ansible folder and 
run the factory provisioning script. This script
sets the hostname and configures a user for the
pimp-my-gimp service. Replace the IP address
with that of your Raspberry Pi.

```console
cd ~/pimp-my-gimp/ansible

ansible-playbook \
  -i inventory.yml \
  --connection=local \
  --extra-vars "raspi_host=192.168.1.100" \
  raspi-factory-init.yml \
  --ask-pass \
  --ask-become
```

When prompted, enter the password for the user 'ubuntu' that you configured in the Raspberry Pi image tool.

The Raspberry Pi may restart at the conclusion of this script. Once it is rebooted, SSH and return to the `pimp-my-gimp/ansible` directory to continue. Run the Ansible provisioning script:

```console
ansible-galaxy install -r roles/requirements.yml

ansible-playbook \
  -i inventory.yml \
  --connection=local \
  --extra-vars "raspi_host=192.168.1.100" \
  scoot-provision.yml
```

Your Raspberry Pi now has the packages and operating system configuration to run pimp-my-gimp. SSH and return to the `pimp-my-gimp/ansible` directory, then run the Ansible script to deploy the application:

```console
ansible-playbook \
  -i inventory.yml \
  --connection=local \
  --extra-vars "raspi_host=192.168.1.100" \
  scoot-deploy.yml
```

### (alternate) Install method 2: Configure from a host controller
If you prefer to provision the Raspberry Pi from a host controller, follow these steps.

Install ansible according to the guide [Installing Ansible](https://docs.ansible.com/ansible/latest/installation_guide/intro_installation.html).

All commands should be run on your local host from the `pimp-my-gimp/ansible` directory. When prompted, enter the password for the user 'ubuntu' that you configured in the Raspberry Pi image tool.

```console
ansible-playbook \
  -i inventory.yml \
  --extra-vars "raspi_host=192.168.1.100" \
  raspi-factory-init.yml \
  --ask-pass \
  --ask-become

ansible-playbook \
  -i inventory.yml \
  --extra-vars "raspi_host=192.168.1.100" \
  scoot-provision.yml

ansible-playbook \
  -i inventory.yml \
  --extra-vars "raspi_host=192.168.1.100" \
  scoot-deploy.yml
```

Replace the IP address with that of your Raspberry Pi.

# Hardware

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
- Amplifier
  - [SparkFun Qwiic Speaker Amp](https://www.sparkfun.com/products/20690)
- Speakers
  - [Sparkfun Thin Speaker - 4 Ohm, 2.5W, 28mm](https://www.sparkfun.com/products/21311)
- Wiring
  - [3.5mm Audio Cable - Male to Male](https://www.amazon.com/3-5mm-CGTime-Plated-Auxiliary-Stereo/dp/B074QHNY5Q)

# Future Features

Ideas for future features: 
- Cupholder
- Measure speed in real-time
- Odometer
- Speed responsive LED track lighting
- Off-road wheels
- Battery assisted drive
- Speed thresholded siren




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