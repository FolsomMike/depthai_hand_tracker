
#
# deviceIdentifierEnum.py
# Author: Mike Schoonover
# Date: 08/21/21
#
# Function:
#
# Defines identifier codes for each device on the different networks.
#
# Some devices are the only device on a given network, so they are easily identified by their ethernet, I2C, or com port
# addresses. Others may share a single serial port and this identifier is used as an address in such case.
#
# All packet headers contain the destination device's identifier and the source device's identifier.
#
#

import enum


class DeviceIdentifierEnum(enum.Enum):

    HEAD_PI = 0
    HEAD_PI_BACKPACK = 1
    MOTOR_CONTROLLER = 2
    HEAD_JETSON_NANO = 3
    OAKDLITE_CONTROLLER = 4

    BROADCAST_TO_ALL = 255
