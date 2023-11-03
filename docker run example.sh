docker run \
    --device /dev/mem:/dev/mem \
    --device /dev/ttyAMA0:/dev/ttyAMA0 \

    # Rather than exposing all of the host's devices
    # to the container, you can be specific and only
    # expose the /dev/gpiomem device to the container
    # at runtime. Be aware that this device needs
    # kernel driver support within the host's Linux
    # distribution. Recent releases of Raspbian should
    # have this. Your mileage with other distributions
    # may vary.
    --device /dev/gpiomem:/dev/gpiomem \
    
    # The Pi's GPIO is represented within the host's
    # file system underneath /sys/class/gpio. This can
    # be accessed with user privileges via the virtual
    # files in that file system. Use Docker volumes to
    # expose this to your container:
    -v /sys:/sys

    # alt based on searchers
    -v /sys/class/gpio:/sys/class/gpio \
    /dev/gpiochip0

pip install pyserial