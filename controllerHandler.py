#!/usr/bin/python3.8 -u

# ----------------------------------------------------------------------------------------------------------------------
#
# controllerHandler.py
# Author: Mike Schoonover
# Date: 07/04/21
#
# Purpose:
#
# Handles interface with a Controller via Ethernet link. Accepts an incoming connection request and then monitors
# the connection for packets from the Controller.
#
# Packets are verified and then made available to client code.
#
# ----------------------------------------------------------------------------------------------------------------------

import os
import time
import sys
import traceback
import numpy as np

from typing import Callable, List, Tuple

import mediapipe_utils as mpu

from spudLink.spudLinkExceptions import SocketBroken
from spudLink.packetTypeEnum import PacketTypeEnum
from spudLink.packetStatusEnum import PacketStatusEnum
from spudLink.packetTool import PacketTool
from spudLink.ethernetLink import EthernetLink


# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# class ControllerHandler
#
# This class handles interfacing with the Controller device.
#


class ControllerHandler:
    # final Charset UTF8_CHARSET = Charset.forName("UTF-8");

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::__init__
    #

    """"
        ControllerHandler initializer.

        :param pThisDeviceIdentifier: a numeric code to identify this device on the network
        :type pThisDeviceIdentifier: int
        :param pRemoteDescriptiveName: a human friendly name for the connected remote device
        :type pRemoteDescriptiveName: str
    """

    def __init__(self, pThisDeviceIdentifier: int, pRemoteDeviceIdentifier: int, pRemoteDescriptiveName: str,
                 pPrepareForProgramShutdownFunction: Callable):

        self.thisDeviceIdentifier: int = pThisDeviceIdentifier

        self.remoteDeviceIdentifier: int = pRemoteDeviceIdentifier

        self.packetTool = PacketTool(self.thisDeviceIdentifier)

        self.prepareForProgramShutdownFunction: Callable = pPrepareForProgramShutdownFunction

        self.ethernetLink = EthernetLink(pRemoteDescriptiveName)

        self.pktRcvCount = 0

        self.waitingForACKPkt: bool = False

    # end of ControllerHandler::__init__
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::getConnected
    #

    def getConnected(self) -> bool:

        """
           Returns the 'connected' flag from EthernetLink which is true if connected to remote and false otherwise.
           :return: 'connected' flag from EthernetLink object
           :rtype: int
        """

        return self.ethernetLink.getConnected()

    # end of ControllerHandler::getConnected
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::setWaitingForACKPkt
    #

    def setWaitingForACKPkt(self, pState: bool):

        self.waitingForACKPkt = pState

    # end of ControllerHandler::setWaitingForACKPkt
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::getWaitingForACKPkt
    #

    def getWaitingForACKPkt(self):

        return self.waitingForACKPkt

    # end of ControllerHandler::getWaitingForACKPkt
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::prepareHandDataForHost
    #

    """
        Sends the hand data to the host controller. This data contains various x/y locations of the key points
        of the palm and digits as well as information about whether a digit is extended or retracted.

        :param pHands:                      a List of HandRegions which contain data about the hands
        :type pHands: List[mpu.HandRegion]
        :param pLandmarkScoreThreshold:     the threshold which the landmark inference score from the AI model must
                                            exceed in order for the data to be considered valid
        :param pLandmarkScoreThreshold: float
        
        :return: a list of lists of tuples which contain data about the hands such as:
                 valid data flag, size of hand boundary, (x,y) coordinates for each keypoint of the palm
        :rtype: List[List[Tuple[int, int]]]

    """

    @staticmethod
    def prepareHandDataForHost(pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float)\
            -> List[List[Tuple[int, int]]]:

        handsData: List[List[Tuple[int, int]]] = []

        for hand in pHands:

            handData: List[Tuple[int, int]] = []

            # first tuple in the series for a hand:
            # (0, 0) -> data invalid due to low inference score
            # (1, 'width of squared hand outline') -> data valid due to adequate inference score

            # the 'width of squared hand outline' value can be used to scale the size of the drawing features, such
            # as line thicknesses and circle diameters

            # noinspection PyUnresolvedReferences
            if hand.lm_score <= pLandmarkScoreThreshold:
                handData.append((0, 0))
            else:
                # noinspection PyUnresolvedReferences
                handData.append((1, round(hand.rect_w_a)))

            # (info_ref_x, info_ref_y): coords in the image of a reference point used to position labels around the
            # hand such as score, handedness, etc.

            # noinspection PyUnresolvedReferences
            labels_ref_x = hand.landmarks[0, 0]
            # noinspection PyUnresolvedReferences
            labels_ref_y = np.max(hand.landmarks[:, 1])

            handData.append((labels_ref_x, labels_ref_y))

            # noinspection PyUnresolvedReferences
            for x, y in hand.landmarks[:, :2]:
                handData.append((x, y))

            handsData.append(handData)

            return handsData

    # end of ControllerHandler::prepareHandDataForHost
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::sendHandDataToHost
    #

    """
        Sends the hand data to the host controller. This data contains various x/y locations of the key points
        of the palm and digits as well as information about whether a digit is extended or retracted.

        :param pHands:                      a List of HandRegions which contain data about the hands
        :type pHands: List[mpu.HandRegion]
        :param pLandmarkScoreThreshold:     the threshold which the landmark inference score from the AI model must
                                            exceed in order for the data to be considered valid
        :param pLandmarkScoreThreshold: float
        
        :return: None
        :rtype: None
    
    """

    def sendHandDataToHost(self, pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float):

        handsData: List[List[Tuple[int, int]]] = []

        handsData = self.prepareHandDataForHost(pHands, pLandmarkScoreThreshold)

    # end of ControllerHandler::sendHandDataToHost
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::doRunTimeTasks
    #

    def doRunTimeTasks(self, pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float) -> int:

        """
            Handles communications and actions with the remote device. This function should be called often during
            runtime to allow for continuous processing.

            If the remote device is not currently connected, then this function will check for connection requests
            and accept the first one to arrive. Afterwards, this function will monitor the incoming data stream for
            packets and process them.

            Currently, only one remote device at a time is allowed to be connected.

            :return: 0 if no operation performed, 1 if an operation performed, -1 on error
            :rtype: int
        """

        try:

            if not self.ethernetLink.getConnected():
                status: int = self.ethernetLink.connectToRemoteIfRequestPending()
                if status == 1:
                    self.packetTool.setStreams(self.ethernetLink.getInputStream(), self.ethernetLink.getOutputStream())
                    return 1
                else:
                    return 0
            else:
                return self.handleCommunications(pHands, pLandmarkScoreThreshold)

        except ConnectionResetError:

            self.logExceptionInformation("Connection Reset Error - Host program probably terminated improperly.")
            self.disconnect()
            return 0

        except SocketBroken:
            self.logExceptionInformation("Host Socket Broken - Host probably closed connection.")
            self.disconnect()
            return 0

    # end of ControllerHandler::doRunTimeTasks
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::handleCommunications
    #

    def handleCommunications(self, pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float) -> int:

        """
            Handles communications with the remote device. This function should be called often during runtime to allow
             for continuous processing.

            This function will monitor the incoming data stream for packets and process them as they are received.

            :return: 0 on no packet handled, 1 on packet handled, -1 on error
                        note that broken or disconnected sockets do NOT return an error as they are handled as a
                        normal part of the process
            :rtype: int

            :raises: SocketBroken:  if socket is broken - probably due to Host closing connection

        """

        self.sendHandDataToHost(pHands, pLandmarkScoreThreshold)

        self.ethernetLink.doRunTimeTasks()

        packetReady: bool = self.packetTool.checkForPacketReady()

        if packetReady:
            return self.handlePacket()

        self.pktRcvCount += 1

        return 0

    # end of ControllerHandler::handleCommunications
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::handlePacket
    #

    def handlePacket(self) -> int:

        """
            Handles a packet received from the remote device.

            :return: 0 on no packet handled, 1 on packet handled, -1 on error
            :rtype: int
        """

        pktType: PacketTypeEnum = self.packetTool.getPktType()

        if pktType is PacketTypeEnum.GET_DEVICE_INFO:

            return self.handleGetDeviceInfoPacket()

        elif pktType == PacketTypeEnum.LOG_MESSAGE:

            # todo mks
            print("Packet received of type: " + pktType.name + "\n")
            return 1

        else:

            return 0

    # end of ControllerHandler::handlePacket
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::handleGetDeviceInfoPacket
    #

    def handleGetDeviceInfoPacket(self) -> int:

        """
            Handles a GET_DEVICE_INFO packet by transmitting a greeting via a LOG_MESSAGE packet back to the remote
            device.

            :return: 0 on no packet handled, 1 on packet handled, -1 on error
            :rtype: int
        """

        print("Packet received of type: GET_DEVICE_INFO")

        self.packetTool.sendString(self.remoteDeviceIdentifier,
                                   PacketTypeEnum.LOG_MESSAGE, "Hello from Oak-D-Lite Camera 1!")

        return 1

    # end of ControllerHandler::handleGetDeviceInfoPacket
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::handleMoveByDistanceAndTimePacket
    #

    def handleMoveByDistanceAndTimePacket(self) -> int:

        """
            Handles a MOVE_BY_DISTANCE_AND_TIME packet by moving the robot the specified distance for the specified
            amount of time in milliseconds, whichever is reached first.

            The speed of each wheel is also parsed from the packet.

            :return: 0 on no packet handled, 1 on packet handled, -1 on error
            :rtype: int
        """

        print("Packet received of type: MOVE_BY_DISTANCE_AND_TIME")

        startPosition: int = 0
        currentPosition: int = 0

        index: int = 0

        pktStatus, index, value = self.packetTool.parseDuplexIntegerFromPacket(index)
        if pktStatus != PacketStatusEnum.PACKET_VALID:
            return -1
        distanceToMove: int = abs(value)

        pktStatus, index, value = self.packetTool.parseDuplexIntegerFromPacket(index)
        if pktStatus != PacketStatusEnum.PACKET_VALID:
            return -1
        timeDurationMS: int = value
        timeDurationSec: float = timeDurationMS / 1000

        pktStatus, index, value = self.packetTool.parseDuplexIntegerFromPacket(index)
        if pktStatus != PacketStatusEnum.PACKET_VALID:
            return -1
        leftWheelSpeed: int = value

        pktStatus, index, value = self.packetTool.parseDuplexIntegerFromPacket(index)
        if pktStatus != PacketStatusEnum.PACKET_VALID:
            return -1
        rightWheelSpeed: int = value

        timeStart: float = time.perf_counter()

        while True:

            #  print("Time: " + str(time.perf_counter()) + " : " + str(timeStart))  # debug mks

            print(str(leftWheelSpeed) + " : " + str(rightWheelSpeed))  # debug mks

            self.setMotorSpeeds(leftWheelSpeed, rightWheelSpeed)

            if time.perf_counter() - timeStart >= timeDurationSec:
                break

            if currentPosition - startPosition >= distanceToMove:
                break

            time.sleep(0.02)

        self.stopMotors()

        # todo mks
        # send ACK packet

        return 1

    # end of ControllerHandler::handleMoveByDistanceAndTimePacket
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::handleShutDownOperatingSystem
    #

    def handleShutDownOperatingSystem(self):

        """
            Handles a SHUT_DOWN_OPERATING_SYSTEM packet by:
                closing all sockets, ports, etc.
                transmitting a response via a LOG_MESSAGE packet back to the remote host
                invoking Operating System shutdown by using a system call

            :return: 0 on no packet handled, 1 on packet handled, -1 on error
            :rtype: int
        """

        print("Packet received of type: SHUT_DOWN_OPERATING_SYSTEM")

        index: int = 0

        pktStatus, index, value = self.packetTool.parseUnsignedByteFromPacket(index)
        if pktStatus != PacketStatusEnum.PACKET_VALID:
            return -1

        # if the data byte is 0 then perform reboot, if 1 then shutdown

        message: str

        if value == 0:
            message = "Rebooting"
        elif value == 1:
            message = "Shutting Down"
        else:
            message = "Shutting Down"

        self.packetTool.sendString(self.remoteDeviceIdentifier, PacketTypeEnum.LOG_MESSAGE,
                                   "Motor Controller says " + message + " Operating System!")

        self.prepareForProgramShutdownFunction()

        # if the data byte is 0 then perform reboot, if 1 then shutdown

        if value == 0:
            os.system("shutdown -r now")
        elif value == 1:
            os.system("shutdown now")
        else:
            os.system("shutdown now")

        sys.exit()

    # end of ControllerHandler::handleShutDownOperatingSystem
    # --------------------------------------------------------------------------------------------------

    def setMotorSpeeds(self, leftWheelSpeed: int, rightWheelSpeed: int):

        # cmdPacket = self.formMagniSpeedMessage(leftWheelSpeed, rightWheelSpeed)

        pass

    # Since stop is so common we have a function to send all stop to the motors

    def stopMotors(self):

        # cmdPacket = self.formMagniSpeedMessage(0, 0)

        pass

    # Form a bytearray holding a speed message with the left and right speed values
    # This routine only handles -254 to 255 speeds but that is generally quite alright

    def formMagniSpeedMessage(self, leftSpeed: int, rightSpeed: int):

        # start with  a speed message for zero speed but without checksum
        speedCmd = [0x7e, 0x3b, 0x2a, 0, 0, 0, 0]

        if rightSpeed < 0:
            speedCmd[3] = 0xff
            speedCmd[4] = (0x100 - ((-1 * rightSpeed) & 0xff)) & 0xff
        else:
            speedCmd[4] = rightSpeed & 0xff

        if leftSpeed < 0:
            speedCmd[5] = 0xff
            speedCmd[6] = (0x100 - ((-1 * leftSpeed) & 0xff)) & 0xff
        else:
            speedCmd[6] = leftSpeed & 0xff

        pktChecksum = self.calcPacketChecksum(speedCmd)
        speedCmd.append(pktChecksum)

        return speedCmd

    # Calculate a packet cheChecksum for the given byte array

    @staticmethod
    def calcPacketChecksum(msgBytes):

        cheChecksum = 0
        idx = 0
        for c in msgBytes:
            if idx > 0:
                cheChecksum += int(c)
            idx += 1
        cheChecksum = 0xff - (cheChecksum & 0xff)
        return cheChecksum

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::disconnect
    #

    def disconnect(self) -> int:

        """
            Disconnects from the Controller device and resets the PacketTool which discards any partially read
            packets.

            :return: 0 if successful, -1 on error
            :rtype: int
        """

        self.packetTool.reset()

        return self.ethernetLink.disconnect()

    # end of ControllerHandler::disconnect
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::logExceptionInformation
    #

    @staticmethod
    def logExceptionInformation(pMessage: str):

        """
            Displays a message, the current Exception name and info, and the traceback info.

            A row of asterisks is printed before and after the info to provide separation.

            :param pMessage: the message to be displayed
            :type pMessage: str
        """

        print("***************************************************************************************")

        print(pMessage)

        print("")

        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_exception(exc_type, exc_value, exc_traceback)

        print("***************************************************************************************")

    # end of ControllerHandler::logExceptionInformation
    # --------------------------------------------------------------------------------------------------

# end of class ControllerHandler
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
#
# //--------------------------------------------------------------------------------------------------
# // BackpackHandler::logMessageFromPacket
# //
# /**
#  * Logs a message received in a packet from a remote device. The message C-string is
#  * extracted from PacketTool.pktDataBuffer and converted to a String. The C-string should have
#  * a null terminator in the packet which is ignored when converting to a string.
#  *
#  */
#
# public void logMessageFromPacket()
# {
#
# 	int numPktDataBytes = packetTool.getNumPktDataBytes();
#
# 	byte[] buf = packetTool.getPktDataBuffer();
#
# 	String message = new String(buf, 0, numPktDataBytes-1);
#
# 	tsLog.appendLine(message);
#
# }//end of BackpackHandler::logMessageFromPacket
# //--------------------------------------------------------------------------------------------------
#
