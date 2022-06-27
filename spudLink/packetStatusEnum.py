
#
# packetStatusEnum.py
# Author: Mike Schoonover
# Date: 08/22/21
#
# Function:
#
# Defines Packet Status codes to define success, failure, corruption, etc. of a packet.
#
#

import enum


class PacketStatusEnum(enum.Enum):

    PACKET_VALID = 0
    UNKNOWN_PACKET_TYPE_ERROR = 1
    DUPLEX_MATCH_ERROR = 2
    LOG_MESSAGE = 3
