
#
# packetTypeEnum.py
# Author: Mike Schoonover
# Date: 07/04/21
#
# Function:
#
# Defines Packet Type codes sent to and received from the Controller device.
#
#

import enum


class PacketTypeEnum(enum.Enum):

    NO_PKT = 0
    ACK_PKT = 1
    GET_DEVICE_INFO = 2
    LOG_MESSAGE = 3

    STOP_ALL_MOTORS = 11
    SET_MOTOR_SPEEDS = 12
    GET_MOTOR_SPEEDS = 13
    GET_ENCODER_VALUES = 14
    MOVE_BY_DISTANCE_AND_TIME = 15
    SHUT_DOWN_OPERATING_SYSTEM = 16
    HAND_GESTURE_DATA = 17
    BATTERY_DATA = 18
