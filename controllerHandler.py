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
import math
import sys
import traceback
import numpy as np
import numpy.typing as npt

from typing import Callable, List, Tuple, Final

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

        self.port: Final[int] = 4243

        self.ethernetLink = EthernetLink(pRemoteDescriptiveName, self.port)

        self.pktRcvCount = 0

        self.waitingForACKPkt: bool = False

        self.handDataSendTimerEnd: float = 0

        self.HAND_DATA_SEND_TIMER_PERIOD: Final[float] = 0.3

        self.MAX_SHORT_INT: Final[int] = 32767

        self.UNKNOWN_DIGIT_POSITION: Final[int] = self.MAX_SHORT_INT
        self.DIGIT_RETRACTED: Final[int] = self.MAX_SHORT_INT - 1
        self.DIGIT_EXTENDED_UP: Final[int] = 0
        self.DIGIT_EXTENDED_SIDE: Final[int] = 90

        # hand directions upwards/sideways

        self.UPWARDS: Final[int] = 0
        self.SIDEWAYS: Final[int] = 1

        # left right handedness

        self.LEFT_HAND: Final[float] = 0.0
        self.RIGHT_HAND: Final[float] = 1.0

        self.LEFT_HAND_INT: Final[int] = 0
        self.RIGHT_HAND_INT: Final[int] = 1

        # index positions of the x,y coordinates

        self.LM_X_COORD: Final[int] = 0
        self.LM_Y_COORD: Final[int] = 1

        # index positions of the landmarks of the digits
        #
        # Example usage to retrieve x,y of tip of thumb:
        #
        # thumbX = hand.landmarks[self.LM_THUMB_TIP][LM_X_COORD]
        # thumbY = hand.landmarks[self.LM_THUMB_TIP][LM_Y_COORD]
        #

        self.LM_PALM_BASE: Final[int] = 0

        self.LM_THUMB_BASE: Final[int] = 1
        self.LM_THUMB_BASE_ABUT: Final[int] = 2
        self.LM_THUMB_TIP_ABUT: Final[int] = 3
        self.LM_THUMB_TIP: Final[int] = 4

        self.LM_INDEX_BASE: Final[int] = 5
        self.LM_INDEX_BASE_ABUT: Final[int] = 6
        self.LM_INDEX_TIP_ABUT: Final[int] = 7
        self.LM_INDEX_TIP: Final[int] = 8

        self.LM_MIDDLE_BASE: Final[int] = 9
        self.LM_MIDDLE_BASE_ABUT: Final[int] = 10
        self.LM_MIDDLE_TIP_ABUT: Final[int] = 11
        self.LM_MIDDLE_TIP: Final[int] = 12

        self.LM_RING_BASE: Final[int] = 13
        self.LM_RING_BASE_ABUT: Final[int] = 14
        self.LM_RING_TIP_ABUT: Final[int] = 15
        self.LM_RING_TIP: Final[int] = 16

        self.LM_LITTLE_BASE: Final[int] = 17
        self.LM_LITTLE_BASE_ABUT: Final[int] = 18
        self.LM_LITTLE_TIP_ABUT: Final[int] = 19
        self.LM_LITTLE_TIP: Final[int] = 20

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
    # ControllerHandler::calculateDistance2Points
    #

    @staticmethod
    def calculateDistance2Points(pA: npt.NDArray[np.float64], pB: npt.NDArray[np.float64]):

        """
            Calculates the distance between two points pA and pB in 2D or 3D.

            :param pA:                          the first point
            :type pA: npt.NDArray[np.float64]

            :param pB:                          the second point
            :type pB: npt.NDArray[np.float64]

            :return:                            the distance between points pA and pB
            :rtype: float

        """

        return np.linalg.norm(pA - pB)

    # end of ControllerHandler::calculateDistance2Points
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::calculateAngleFrom3Points
    #

    @staticmethod
    def calculateAngleFrom3Points(pA, pB, pC):

        """
            Calculates the angle formed from three points pA, pB, and pC.

            :param pA:                          the first point
            :type pA: npt.NDArray[np.float64]

            :param pB:                          the second point
            :type pB: npt.NDArray[np.float64]

            :param pC:                          the third point
            :type pC: npt.NDArray[np.float64]

            :return:                            the distance between points pA and pB
            :rtype: float

            Reference:

            https://stackoverflow.com/questions/35176451/python-code-to-calculate-angle-between-three-point-using-
            their-3d-coordinates

        """

        # a, b and c : points as np.array([x, y, z])

        ba = pA - pB
        bc = pC - pB
        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.arccos(cosine_angle)

        return np.degrees(angle)

    # end of ControllerHandler::calculateAngleFrom3Points
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::calculateAngleOfLineInDegrees
    #

    @staticmethod
    def calculateAngleOfLineInDegrees(pX1: int, pY1: int, pX2: int, pY2: int) -> float:

        """

            Calculates the angle of a line in degrees. The line is specified by the endpoints pX1,pY1 to pX2,pY2.

            :param pX1:                      x coordinate of the starting endpoint of the line
            :type: float

            :param pY1:                      y coordinate of the starting endpoint of the line
            :type: float

            :param pX2:                      x coordinate of the ending endpoint of the line
            :type: float

            :param pY2:                      y coordinate of the ending endpoint of the line
            :type: float

           :return: the angle of the line from 0~360 degrees
           :rtype: float

        """

        dx: float = pX2 - pX1
        dy: float = pY2 - pY1

        theta = math.atan2(dy, dx)
        angle = math.degrees(theta)  # angle is in (-180, 180]

        if angle < 0:
            angle += 360

        return angle

    # end of ControllerHandler::calculateAngleOfLineInDegrees
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::inferDirectionOfHand
    #

    def inferDirectionOfHand(self, pHand: mpu.HandRegion) -> int:

        """

            Infers the direction of the hand as upwards or sideways based on relative positions and angles of the
            landmarks.

            When hands are held sideways, it is assumed that the fingers are pointing inward (towards the opposite
            hand). It is uncomfortable to point the fingers outwards from the body or downwards with the palms facing
            the camera, so those options are ignored.

            Possible results (assumes palms facing camera):

                self.UPWARDS   -> fingers upward
                self.SIDEWAYS  -> fingers sideways (towards center of both hands)

            :param pHand:                      a HandRegion which contains data about a hand
            :type: mpu.HandRegion

           :return: the angle of the hand: self.UPWARDS -> fingers upwards; self.SIDEWAYS -> fingers sideways
           :rtype: int

        """

        # calculate angle of the line from base joint of index finger to base joint of little finger

        indexBaseX = pHand.landmarks[self.LM_INDEX_BASE][self.LM_X_COORD]
        indexBaseY = pHand.landmarks[self.LM_INDEX_BASE][self.LM_Y_COORD]

        littleBaseX = pHand.landmarks[self.LM_LITTLE_BASE][self.LM_X_COORD]
        littleBaseY = pHand.landmarks[self.LM_LITTLE_BASE][self.LM_Y_COORD]

        handAngle: float = self.calculateAngleOfLineInDegrees(indexBaseX, indexBaseY, littleBaseX, littleBaseY)

        handDirection: int

        if 45 < handAngle < 135:
            handDirection = self.SIDEWAYS
        else:
            handDirection = self.UPWARDS

        return handDirection

    # end of ControllerHandler::inferDirectionOfHand
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::translateLandmarksToThumbPosition
    #

    def translateLandmarksToThumbPosition(self, pHand: mpu.HandRegion, pHandDirection: int):

        """
            Infers the state of the thumb based on relative positions of the landmarks of each thumb.

            Stores the result in pHand.thumb_state.

            When hand is held upwards, the x coordinates of the tip of the thumb and the joint next to the tip
            (the abutting joint) are used to determine if the thumb is extended or not.

            See translateLandmarksToDigitPositions for more details.

            :param pHand:                      a HandRegion which contains data about a hand
            :type pHand: mpu.HandRegion

            :param pHandDirection:             direction hand is pointing, self.UPWARDS or self.SIDEWAYS
            :type pHandDirection: int

        """

        thumbTipX: int = pHand.landmarks[self.LM_THUMB_TIP][self.LM_X_COORD]
        thumbTipY: int = pHand.landmarks[self.LM_THUMB_TIP][self.LM_Y_COORD]
        thumbTipAbutX: int = pHand.landmarks[self.LM_THUMB_TIP_ABUT][self.LM_X_COORD]
        thumbTipAbutY: int = pHand.landmarks[self.LM_THUMB_TIP_ABUT][self.LM_Y_COORD]

        pHand.thumb_state = self.DIGIT_RETRACTED

        if pHand.handedness == self.LEFT_HAND:

            if pHandDirection == self.UPWARDS:
                if thumbTipX < thumbTipAbutX:
                    pHand.thumb_state = self.DIGIT_EXTENDED_SIDE
                    return
                else:
                    pHand.thumb_state = self.DIGIT_RETRACTED
                    return
            else:  # hand held sideways
                if thumbTipY < thumbTipAbutY:
                    pHand.thumb_state = self.DIGIT_EXTENDED_UP
                    return
                else:
                    pHand.thumb_state = self.DIGIT_RETRACTED
                    return

        else:  # right hand

            if pHandDirection == self.UPWARDS:
                if thumbTipX > thumbTipAbutX:
                    pHand.thumb_state = self.DIGIT_EXTENDED_SIDE
                    return
                else:
                    pHand.thumb_state = self.DIGIT_RETRACTED
                    return
            else:  # hand held sideways
                if thumbTipY < thumbTipAbutY:
                    pHand.thumb_state = self.DIGIT_EXTENDED_UP
                    return
                else:
                    pHand.thumb_state = self.DIGIT_RETRACTED
                    return

    # end of ControllerHandler::translateLandmarksToThumbPosition
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::translateLandmarksToDigitPositions
    #

    def translateLandmarksToDigitPositions(self, pHand: mpu.HandRegion):

        """
            Infers the state of each digit based on relative positions of the landmarks of each digit as well as the
            angle of the line between appropriate landmarks.

            This version uses hand.landmarks instead of hand.norm_landmarks. The norm set has the hand always rotated
            with fingers upwards, even if they are being held downwards. Since we only want gestures to be recognized
            when the hands are oriented upward to avoid unwanted signals, the un-rotated version is used to parse
            gestures. A downward hand returns as the gesture 'zero'.

            Also infers left hand vs right hand based on positions of thumb and little finger. This is only accurate
            if palms are facing camera. The HandRegion.handedness value is overwritten to signal left/right:
                0.0 = left, 1.0 = right

            Note that this is method is different than used by mediapipe to set the HandRegion.handedness...they use
            AI model results to determine left/right - it is a bit less accurate, but works regardless of whether the
            palm/back of hand is facing the camera.

            The state of the digits are encoded as follows:

                32767   unknown state ~ cannot be inferred
                32766   retracted
                0       extended 0 degrees straight up
                45      extended and rotated  45 degrees CCW from straight up
                90      extended and rotated  90 degrees CCW from straight up
                135     extended and rotated 135 degrees CCW from straight up
                180     extended and rotated 180 degrees CCW from straight up - pointing straight down

                -45     extended and rotated  45 degrees CW from straight up
                -90     extended and rotated  90 degrees CW from straight up
                -135    extended and rotated 135 degrees CW from straight up

            :param pHand:                      a HandRegion which contains data about a hand
            :type pHand: mpu.HandRegion

        """

        # infer left or right hand based on relative positions of the X coordinates of the bases of the thumb and
        # the little finger (only accurate if palms facing camera) - if thumb is left of little finger on the screen,
        # it is the left hand, otherwise it is right hand
        # note that the hands are mirrored on the screen in relation to the person viewing their hands

        #   value [5][0]  is the X coordinate ([0]) of the base of the thumb ([5])
        #   value [20][0] is the X coordinate ([0]) of the base of the little finger ([20])

        if pHand.landmarks[5][0] < pHand.landmarks[20][0]:
            pHand.handedness = self.LEFT_HAND
        else:
            pHand.handedness = self.RIGHT_HAND

        whichHand: str

        handDirection: int = self.inferDirectionOfHand(pHand)

        self.translateLandmarksToThumbPosition(pHand, handDirection)

        # infer finger states from relative positions of each digit's landmarks

        if pHand.landmarks[8][1] < pHand.landmarks[7][1] < pHand.landmarks[6][1]:
            pHand.index_state = self.DIGIT_EXTENDED_UP
        elif pHand.landmarks[6][1] < pHand.landmarks[8][1]:
            pHand.index_state = self.DIGIT_RETRACTED
        else:
            pHand.index_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.landmarks[12][1] < pHand.landmarks[11][1] < pHand.landmarks[10][1]:
            pHand.middle_state = self.DIGIT_EXTENDED_UP
        elif pHand.landmarks[10][1] < pHand.landmarks[12][1]:
            pHand.middle_state = self.DIGIT_RETRACTED
        else:
            pHand.middle_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.landmarks[16][1] < pHand.landmarks[15][1] < pHand.landmarks[14][1]:
            pHand.ring_state = self.DIGIT_EXTENDED_UP
        elif pHand.landmarks[14][1] < pHand.landmarks[16][1]:
            pHand.ring_state = self.DIGIT_RETRACTED
        else:
            pHand.ring_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.landmarks[20][1] < pHand.landmarks[19][1] < pHand.landmarks[18][1]:
            pHand.little_state = self.DIGIT_EXTENDED_UP
        elif pHand.landmarks[18][1] < pHand.landmarks[20][1]:
            pHand.little_state = self.DIGIT_RETRACTED
        else:
            pHand.little_state = self.UNKNOWN_DIGIT_POSITION

        # wip mks ~ for now always retracted for hand held sideways...in future, look at x locs instead of y locs for
        # finger states in the above code

        if handDirection == self.SIDEWAYS:
            pHand.index_state = self.DIGIT_RETRACTED
            pHand.middle_state = self.DIGIT_RETRACTED
            pHand.ring_state = self.DIGIT_RETRACTED
            pHand.little_state = self.DIGIT_RETRACTED

    # end of ControllerHandler::translateLandmarksToDigitPositions
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::inferFingerPositions
    #

    def inferFingerPositions(self, pHand: mpu.HandRegion):

        """
            Uses the x,y positions of the finger/thumb landmarks to determine if each digit is extended or retracted
            and the angle from tip-to-base of each extended digit.

            Note that the normally extended thumb will be inferred at 90 or -90 degrees (pointing sideways).

            All digits for pHand are decoded.

            The state of the digits are encoded as follows:

                32767   unknown state ~ cannot be inferred
                32766   retracted
                0       extended 0 degrees straight up
                45      extended and rotated  45 degrees CCW from straight up
                90      extended and rotated  90 degrees CCW from straight up
                135     extended and rotated 135 degrees CCW from straight up
                180     extended and rotated 180 degrees CCW from straight up - pointing straight down

                -45     extended and rotated  45 degrees CW from straight up
                -90     extended and rotated  90 degrees CW from straight up
                -135    extended and rotated 135 degrees CW from straight up

            :param pHand:                      a HandRegion which contains data about a hand
            :type pHand: mpu.HandRegion

        """

        # decode the hand digit positions

        self.translateLandmarksToDigitPositions(pHand)

        # translate mediapipe codes to digit pointing angles

        if pHand.thumb_state == 0:
            pHand.thumb_state = self.DIGIT_RETRACTED
        elif pHand.thumb_state == 1:
            pHand.thumb_state = 90   # todo mks ~ will be 90 or -90
        else:
            pHand.thumb_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.index_state == 0:
            pHand.index_state = self.DIGIT_RETRACTED
        elif pHand.index_state == 1:
            pHand.index_state = 0
        else:
            pHand.index_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.middle_state == 0:
            pHand.middle_state = self.DIGIT_RETRACTED
        elif pHand.middle_state == 1:
            pHand.middle_state = 0
        else:
            pHand.middle_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.ring_state == 0:
            pHand.ring_state = self.DIGIT_RETRACTED
        elif pHand.ring_state == 1:
            pHand.ring_state = 0
        else:
            pHand.ring_state = self.UNKNOWN_DIGIT_POSITION

        if pHand.little_state == 0:
            pHand.little_state = self.DIGIT_RETRACTED
        elif pHand.little_state == 1:
            pHand.little_state = 0
        else:
            pHand.little_state = self.UNKNOWN_DIGIT_POSITION

    # end of ControllerHandler::inferFingerPositions
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::prepareHandDataForHost
    #

    """
        Prepares data for all hands for sending to the host. This data contains various x/y locations of the key points
        of the palm and digits as well as information about whether a digit is extended or retracted.
        
        Each x,y point is contained in a Tuple. This method returns a List of Tuples of all the data from all hands.
        
        The data block in the packet to the host is a series of signed short ints (16 bits) as follows:
        
        byte        name            purpose
        
            (first hand starts at byte 0)
         
              0:1    valid data      0 if data is invalid, 1 if data is valid
              2:3    hand width      0 if data is invalid, the width of the bounding square around the hand if valid
            
              4:5    thumb state     unknown/retracted/extended pointing angle state of the thumb      
              6:7    index state     unknown/retracted/extended pointing angle state of the index finger
              8:9    middle state    unknown/retracted/extended pointing angle state of the middle finger        
             10:11   ring state      unknown/retracted/extended pointing angle state of the ring finger
             12:13   little state    unknown/retracted/extended pointing angle state of the little finger
             14:15   which hand      0 for left hand, 1 for right; only works with palms facing camera
            
             16:17   x label anchor  x coordinate anchor point useful for positioning labels drawn around the hand
             18:19   y label anchor  y coordinate anchor point useful for positioning labels drawn around the hand
            
             20:21   x of palm base  x coordinate of the base of the palm near to the wrist   
             22:23   y of palm base  y coordinate of the base of the palm near to the wrist
            
             24:25   x0 of thumb     x coordinate of point 0 of the thumb (base)
             26:27   y0 of thumb     y coordinate of point 0 of the thumb (base)
             28:29   x1 of thumb     x coordinate of point 1 of the thumb
             30:31   y1 of thumb     y coordinate of point 1 of the thumb
             32:33   x2 of thumb     x coordinate of point 2 of the thumb
             34:35   y2 of thumb     y coordinate of point 2 of the thumb
             36:37   x3 of thumb     x coordinate of point 3 of the thumb (tip)
             38:39   y3 of thumb     y coordinate of point 3 of the thumb (tip)

             40:41   x0 of index     x coordinate of point 0 of the index (base)
             42:43   y0 of index     y coordinate of point 0 of the index (base)
             44:45   x1 of index     x coordinate of point 1 of the index
             46:47   y1 of index     y coordinate of point 1 of the index
             48:49   x2 of index     x coordinate of point 2 of the index
             50:51   y2 of index     y coordinate of point 2 of the index
             52:53   x3 of index     x coordinate of point 3 of the index (tip)
             54:55   y3 of index     y coordinate of point 3 of the index (tip)

             56:57   x0 of middle    x coordinate of point 0 of the middle (base)
             58:59   y0 of middle    y coordinate of point 0 of the middle (base)
             60:61   x1 of middle    x coordinate of point 1 of the middle
             62:63   y1 of middle    y coordinate of point 1 of the middle
             64:65   x2 of middle    x coordinate of point 2 of the middle
             66:67   y2 of middle    y coordinate of point 2 of the middle
             68:69   x3 of middle    x coordinate of point 3 of the middle (tip)
             70:71   y3 of middle    y coordinate of point 3 of the middle (tip)

             72:73   x0 of ring      x coordinate of point 0 of the ring (base)
             74:75   y0 of ring      y coordinate of point 0 of the ring (base)
             76:77   x1 of ring      x coordinate of point 1 of the ring
             78:79   y1 of ring      y coordinate of point 1 of the ring
             80:81   x2 of ring      x coordinate of point 2 of the ring
             82:83   y2 of ring      y coordinate of point 2 of the ring
             84:85   x3 of ring      x coordinate of point 3 of the ring (tip)
             86:87   y3 of ring      y coordinate of point 3 of the ring (tip)

             88:89   x0 of little    x coordinate of point 0 of the little (base)
             90:91   y0 of little    y coordinate of point 0 of the little (base)
             92:93   x1 of little    x coordinate of point 1 of the little
             94:95   y1 of little    y coordinate of point 1 of the little
             96:97   x2 of little    x coordinate of point 2 of the little
             98:99   y2 of little    y coordinate of point 2 of the little
            100:101  x3 of little    x coordinate of point 3 of the little (tip)
            102:103  y3 of little    y coordinate of point 3 of the little (tip)

            (next hand starts at byte 104)
            
            104:105  valid data      0 if data is invalid, 1 if data is valid
            106:107  hand width      0 if data is invalid, the width of the bounding square around the hand if valid
            ...
            ...                 { duplicate of first hand...refer to above }
            ...


        :param pHands:                      a List of HandRegions which contain data about the hands
        :type pHands: List[mpu.HandRegion]
        :param pLandmarkScoreThreshold:     the threshold which the landmark inference score from the AI model must
                                            exceed in order for the data to be considered valid
        :param pLandmarkScoreThreshold: float
        
        :return: a list of Tuples which contain data about all hands such as:
                 valid data flag, size of hand boundary, (x,y) coordinates for each keypoint of the palm
        :rtype: List[Tuple[int, int]]

    """

    # noinspection PyUnresolvedReferences

    def prepareHandDataForHost(self, pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float)\
            -> List[Tuple[int, int]]:

        handsData: List[Tuple[int, int]] = []

        for hand in pHands:

            # first tuple in the series for a hand:
            # (0, 0) -> data invalid due to low inference score
            # (1, 'width of squared hand outline') -> data valid due to adequate inference score

            # the 'width of squared hand outline' value can be used to scale the size of the drawing features, such
            # as line thicknesses and circle diameters

            # noinspection PyUnresolvedReferences
            if hand.lm_score <= pLandmarkScoreThreshold:
                handsData.append((0, 0))
            else:
                # noinspection PyUnresolvedReferences
                handsData.append((1, round(hand.rect_w_a)))

            # add the digit extended/retracted states to the list

            # infer the state of the digits for use in inferring gestures
            self.translateLandmarksToDigitPositions(hand)

            if hand.handedness == self.LEFT_HAND:
                whichHand = self.LEFT_HAND_INT
            else:
                whichHand = self.RIGHT_HAND_INT

            handsData.append((hand.thumb_state, hand.index_state))
            handsData.append((hand.middle_state, hand.ring_state))
            handsData.append((hand.little_state, whichHand))

            # add the x,y coordinate used as an anchor point for any labels

            # (info_ref_x, info_ref_y): coords in the image of a reference point used to position labels around the
            # hand such as score, handedness, etc.

            # noinspection PyUnresolvedReferences
            labels_ref_x = hand.landmarks[0, 0]
            # noinspection PyUnresolvedReferences
            labels_ref_y = np.max(hand.landmarks[:, 1])

            handsData.append((labels_ref_x, labels_ref_y))

            # add the x,y coordinates for each landmark key point

            # hand.landmarks[0][0] = 10  # debug mks
            # hand.landmarks[0][1] = 100  # debug mks

            # noinspection PyUnresolvedReferences
            for x, y in hand.landmarks[:, :2]:
                handsData.append((x, y))

        return handsData

    # end of ControllerHandler::prepareHandDataForHost
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # ControllerHandler::sendHandDataToHost
    #

    """
        Sends the hand data to the host controller. This data contains various x/y locations of the key points
        of the palm and digits as well as information about whether a digit is extended or retracted.
        
        If pHands is empty, no data will be sent. If it contains info for one hand, data for that one hand will be
        sent. For two hands, data for both will be sent. The host can determine the number of hands by the number of
        data bytes in the packet.
        
        The handedness is not specified. If both hands are on the screen, the first hand sent will be the left one
        on the camera image.
        
        Will only send data if HAND_DATA_SEND_TIMER_PERIOD number of seconds have passed since the last transmission.

        :param pHands:                      a List of HandRegions which contain data about the hands
        :type pHands: List[mpu.HandRegion]
        :param pLandmarkScoreThreshold:     the threshold which the landmark inference score from the AI model must
                                            exceed in order for the data to be considered valid
        :param pLandmarkScoreThreshold: float
    
    """

    def sendHandDataToHost(self, pHands: List[mpu.HandRegion], pLandmarkScoreThreshold: float):

        nowTime: float = time.perf_counter()

        if nowTime < self.handDataSendTimerEnd:
            return

        self.handDataSendTimerEnd = nowTime + self.HAND_DATA_SEND_TIMER_PERIOD

        handsData: List[Tuple[int, int]]

        handsData = self.prepareHandDataForHost(pHands, pLandmarkScoreThreshold)

        # debugMKS = [(1, 2), (3, 4)] remove this

        self.packetTool.sendSignedShortIntsFromListOfTuples(
            self.remoteDeviceIdentifier,
            PacketTypeEnum.HAND_GESTURE_DATA, handsData)

        # print("transmit hand data")   # debug mks

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

        except ConnectionAbortedError:

            self.logExceptionInformation("Connection Aborted Error - Host program probably terminated improperly.")
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
