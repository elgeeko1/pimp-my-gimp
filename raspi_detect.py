import io
import os

def read_is_raspi():
    """
    Checks if the current system is a Raspberry Pi.

    Returns:
        bool: True if the system is a Raspberry Pi, False otherwise.
    """

    # Check if the operating system is POSIX compliant (Linux, Unix, etc.)
    if os.name != 'posix':
        return False

    # List of Raspberry Pi hardware identifiers
    raspberry_pi_chips = ('BCM2708', 'BCM2709', 'BCM2711', 'BCM2835', 'BCM2836')

    try:
        # Open the CPU information file to read hardware details
        with io.open('/proc/cpuinfo', 'r') as cpuinfo_file:
            for line in cpuinfo_file:
                # Look for the line that starts with 'Hardware'
                if line.startswith('Hardware'):
                    # Extract the hardware identifier
                    _, hardware_value = line.strip().split(':', 1)
                    hardware_value = hardware_value.strip()

                    # Check if the identifier is in the list of Raspberry Pi chips
                    if hardware_value in raspberry_pi_chips:
                        return True
    except Exception:
        # In case of any exception, pass without doing anything
        pass

    # Return False if it's not a Raspberry Pi
    return False

is_raspi = read_is_raspi()