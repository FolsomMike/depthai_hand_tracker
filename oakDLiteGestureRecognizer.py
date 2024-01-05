#!/usr/bin/env python3

# --------------------------------------------------------------------------------------------------
#
# ~ How to run this in PyCharm ~
#
# This WILL run in PyCharm on Windows with the Oak-D-Lite connected to USB-C port.
#
# In the lower left corner of PyCharm, click 'All Services'. There are multiple run configurations listed, each
# with different command line parameters passed to the program on start:
#
# with video ~ shows skeleton hands over video, some processing done on computer
#
# no video - hand skeleton only ~ shows skeleton hands only, no video shown, ALL processing done on camera unit (edge
#        mode)
#
# server mode - no display at all, sends data to host ~ no skeleton hands drawn, no video shown,  ALL processing done
#       on camera unit (edge mode), data is sent to Ethernet host without display by this program
#
# oakDLiteGestureRecognizer ~ this one might reappear, not used, can be deleted ~ no command line parameters
#
# ~ Connecting from Spud Main Pi on the same Windows Computer ~
#
# Edit 'profile selection.config' in the Main Pi program root folder and select profile:
#
#       hardware profile=on the debug computer with Local Simulated Devices
#
# Start this program in PyCharm and then start the Main Pi program and 'Connect' in the Oak-D-Lite menu.
#
import sys

import cv2

from HandTrackerRenderer import HandTrackerRenderer
import argparse

from typing import Final

from spudLink.deviceIdentifierEnum import DeviceIdentifierEnum

from controllerHandler import ControllerHandler

# simple version string
g_version = "MKS0625212331"

# --------------------------------------------------------------------------------------------------
# ::prepareForProgramShutdown
#
# Prepares for the program to be shut down by closing ports and releasing resources.
#


def prepareForProgramShutdown():

    controllerHandler.disconnect()
    # logAlways("Host controller ethernet port closed...")

# end of ::prepareForProgramShutdown
# --------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# ::setupControllerHandler
#


def setupControllerHandler() -> ControllerHandler:
    """
        Creates and prepares the ControllerHandler object for use. This object handles communications with the host
        controller device.

        :return: a reference to the ControllerHandler object
        :rtype: ControllerHandler
    """

    REMOTE_DEVICE_ADDRESS: Final[int] = DeviceIdentifierEnum.HEAD_PI.value
    THIS_DEVICE_ADDRESS: Final[int] = DeviceIdentifierEnum.OAKDLITE_CONTROLLER.value
    REMOTE_DESCRIPTIVE_NAME: Final[str] = "Spud Head Pi"
    handler = ControllerHandler(THIS_DEVICE_ADDRESS, REMOTE_DEVICE_ADDRESS, REMOTE_DESCRIPTIVE_NAME,
                                prepareForProgramShutdown)

    return handler

# end of ::setupControllerHandler
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# ::doRunTimeTasks
#


def doRunTimeTasks(pControllerHandler: ControllerHandler):

    """
        Performs all run time tasks.

        :return: 0 on success, -1 on error
        :rtype: int
    """

    while True:

        # Run hand tracker on next frame
        # 'bag' contains some information related to the frame
        # and not related to a particular hand like body keypoints in Body Pre Focusing mode
        # Currently 'bag' contains meaningful information only when Body Pre Focusing is used

        frame, hands, bag = tracker.next_frame()

        if frame is None:
            break

        numMotionBlocksDetected: int = 0

        key = 0

        if args.hand_gestures_and_motion_detection:
            # do motion check FIRST or the quivering gesture annotations will cause motion detection
            numMotionBlocksDetected = pControllerHandler.checkForMovementOnVideoFrame(frame)
            renderer.draw(frame, hands, bag)
            key = renderer.waitKey()

        status = pControllerHandler.doRunTimeTasks(hands, tracker.lm_score_thresh, numMotionBlocksDetected)
        if status < 0:
            return status

        # in server mode, nothing is displayed by this program but data is sent to host controller

        if args.hand_gestures:
            if not args.display_locally:
                key = cv2.waitKey(1)
            else:
                renderer.draw(frame, hands, bag)
                key = renderer.waitKey()

        if key == 27 or key == ord('q'):
            return 0

# end of ::doRunTimeTasks
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# ::validateRuntimeParameters
#


"""

    Detects errors in the runtime parameters, such as illegal combinations.
    
    :return: true if parameters valid, false on error
    :rtype: bool

"""


def validateRuntimeParameters() -> bool:

    # must specify at least one mode: hand gesture OR hand gesture + motion detection

    if not args.hand_gestures and not args.hand_gestures_and_motion_detection:
        print("Error -> must specify one: --hand_gestures OR --hand_gestures_and_motion_detection")
        return False

    # must either specify hand gesture OR hand gesture + motion detection

    if args.hand_gestures and args.hand_gestures_and_motion_detection:
        print("Error -> cannot specify both --hand_gestures --hand_gestures_and_motion_detection")
        return False

    # input = rgb_laconic mode does not return video therefore it cannot be checked for motion

    if args.hand_gestures_and_motion_detection and args.input == "rgb_laconic":
        print("Error-> cannot specify both --hand_gestures_and_motion_detection and input=rbg_laconic")
        return False

    return True

# end of ::validateRuntimeParameters
# ----------------------------------------------------------------------------------------------------------------------

# ----------------------------------------------------------------------------------------------------------------------
# ::__main__
#


parser = argparse.ArgumentParser()

parser.add_argument('-e', '--edge', action="store_true",
                    help="Use Edge mode (most/all postprocessing runs on the Oak device)")

parser_tracker = parser.add_argument_group("Tracker arguments")

parser_tracker.add_argument('--display_locally', action="store_true",
                            help="Video from the Oak camera is displayed on the local machine but requires more CPU "
                                 "time.")

parser_tracker.add_argument('--hand_gestures', action="store_true", help="Detects hand gestures.")

parser_tracker.add_argument('--hand_gestures_and_motion_detection', action="store_true",
                            help="Detects both hand gestures and movement.")

parser_tracker.add_argument('-i', '--input', type=str,
                            help="Path to video or image file to use as input (if not specified, use OAK color camera)")
parser_tracker.add_argument("--pd_model", type=str,
                            help="Path to a blob file for palm detection model")
parser_tracker.add_argument('--no_lm', action="store_true", 
                            help="Only the palm detection model is run (no hand landmark model)")
parser_tracker.add_argument("--lm_model", type=str,
                            help="Landmark model 'full', 'lite', 'sparse' or path to a blob file")
parser_tracker.add_argument('--use_world_landmarks', action="store_true", 
                            help="Fetch landmark 3D coordinates in meter")
parser_tracker.add_argument('-s', '--solo', action="store_true", 
                            help="Solo mode: detect one hand max. If not used, detect 2 hands max (Duo mode)")
parser_tracker.add_argument('-xyz', "--xyz", action="store_true", 
                            help="Enable spatial location measure of palm centers")
parser_tracker.add_argument('-g', '--gesture', action="store_true", 
                            help="Enable gesture recognition")
parser_tracker.add_argument('-c', '--crop', action="store_true", 
                            help="Center crop frames to a square shape")
parser_tracker.add_argument('-f', '--internal_fps', type=int, 
                            help="Fps of internal color camera. Too high value lower NN fps (default= depends on the "
                                 "model)")
parser_tracker.add_argument("-r", "--resolution", choices=['full', 'ultra'], default='full',
                            help="Sensor resolution: 'full' (1920x1080) or 'ultra' (3840x2160) (default=%(default)s)")
parser_tracker.add_argument('--internal_frame_height', type=int,                                                                                 
                            help="Internal color camera frame height in pixels")
parser_tracker.add_argument("-lh", "--use_last_handedness", action="store_true",
                            help="Use last inferred handedness. Otherwise use handedness average (more robust)")
parser_tracker.add_argument('--single_hand_tolerance_thresh', type=int, default=10,
                            help="(Duo mode only) Number of frames after only one hand is detected before calling "
                                 "palm detection (default=%(default)s)")
parser_tracker.add_argument('--dont_force_same_image', action="store_true",
                            help="(Edge Duo mode only) Don't force the use the same image when inferring the "
                                 "landmarks of the 2 hands (slower but skeleton less shifted)")
parser_tracker.add_argument('-lmt', '--lm_nb_threads', type=int, choices=[1, 2], default=2,
                            help="Number of the landmark model inference threads (default=%(default)i)")
parser_tracker.add_argument('-t', '--trace', type=int, nargs="?", const=1, default=0, 
                            help="Print some debug infos. The type of info depends on the optional argument.")

parser_renderer = parser.add_argument_group("Renderer arguments")
parser_renderer.add_argument('-o', '--output', 
                             help="Path to output video file")

args = parser.parse_args()

if not validateRuntimeParameters():
    sys.exit(1)

# copy a subset of the parser_renderer args to tracker_args for use by HandTracker

dargs = vars(args)
tracker_args = \
    {a: dargs[a] for a in ['pd_model', 'lm_model', 'internal_fps', 'internal_frame_height'] if dargs[a] is not None}

if args.edge:
    from HandTrackerEdge import HandTracker
    # 'use_same_image' flag is ONLY allowed with HandTrackerEdge for some reason
    tracker_args['use_same_image'] = not args.dont_force_same_image
else:
    from HandTracker import HandTracker

tracker = HandTracker(
        input_src=args.input, 
        use_lm=not args.no_lm,
        use_world_landmarks=args.use_world_landmarks,
        use_gesture=args.gesture,
        xyz=args.xyz,
        solo=args.solo,
        crop=args.crop,
        resolution=args.resolution,
        stats=True,
        trace=args.trace,
        use_handedness_average=not args.use_last_handedness,
        single_hand_tolerance_thresh=args.single_hand_tolerance_thresh,
        lm_nb_threads=args.lm_nb_threads,
        **tracker_args
        )

renderer = HandTrackerRenderer(tracker=tracker, pDisplayLocally=args.display_locally, output=args.output)

controllerHandler: ControllerHandler = setupControllerHandler()

doRunTimeTasks(controllerHandler)

renderer.exit()

tracker.exit()

controllerHandler.disconnect()

# end of ::__main__
# ----------------------------------------------------------------------------------------------------------------------
