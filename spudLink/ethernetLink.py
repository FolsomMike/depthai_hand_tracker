#!/usr/bin/python3.8 -u

# ----------------------------------------------------------------------------------------------------------------------
#
# ethernetLink.py
# Author: Mike Schoonover
# Date: 07/09/21
#
# Purpose:
#
# This class handles the link to a remote device via Ethernet connections. The remote device is expected to initiate the
# connection; this class watches for and accepts requests to connect.
#
# Open Source Policy:
#
# This source code is Public Domain and free to any interested party.  Any
# person, company, or organization may do with it as they please.
#
# ----------------------------------------------------------------------------------------------------------------------

from typing import Final, List, Tuple, Optional  # also available: Set, Dict, Tuple, Optional

import select
import socket

from .spudLinkExceptions import SocketBroken
from .circularBuffer import CircularBuffer

# https://mypy.readthedocs.io/en/stable/cheat_sheet_py3.html

RECEIVE_BUFFER_SIZE: Final[int] = 50    # debug mks ~ increase this to 1024 or so

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# class EthernetLink
#
# This class handles the link to a remote device via Ethernet connections.
#


class EthernetLink:

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::__init__
    #

    def __init__(self, pRemoteDescriptiveName: str):

        """
            EthernetLink initializer.

            :param pRemoteDescriptiveName: a human friendly name for the connected remote device
            :type pRemoteDescriptiveName: str
        """

        self.remoteDescriptiveName = pRemoteDescriptiveName
        self.connected: bool = False

        self.receiveBuf = CircularBuffer(RECEIVE_BUFFER_SIZE)

        self.clientSocket: Optional[socket.socket] = None
        self.clientSocketList: List[socket.socket] = []

        # remoteAddress -> (remote Address, remote port)
        self.remoteAddress: Tuple[str, int] = ("", 0)

        # todo mks ~ 4243 should NOT be hardcoded...client code should inject!

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', 4243))
        self.server_socket.listen(1)
        self.server_socket_list: List[socket.socket] = [self.server_socket]

        print("Listening for Ethernet connection request on port 4243.")

    # end of EthernetLink::__init__
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::doRunTimeTasks
    #

    def doRunTimeTasks(self) -> int:

        """
            Handles ongoing tasks associated with the socket stream such as reading data and storing in a buffer.

            :return: 0 on success, -1 on error
            :rtype: int

        """

        if not self.connected:
            return 0

        self.handleReceive()

        return 0

    # end of EthernetLink::doRunTimeTasks
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::handleReceive
    #
    # This function reads all available bytes from the stream and stores them in a circular buffer.
    #
    # Strangely (and stupidly) enough, Python does not have a simple method to check if bytes are available in the
    # socket (such as Java's bytesAvailable). Thus, attempting to read an empty blocking socket will hang until data is
    # ready or until a timeout value is reached.
    #
    # This issue is handled here by calling select.select which will return a list containing socket(s) with data ready.
    # For this program, the socket is left as blocking and the normally blocking call to select is made non-blocking by
    # specifying a timeout of 1. This will allow for a quick check to see if at least one byte is ready.
    #

    def handleReceive(self):

        inputs = [self.clientSocket]
        outputs = [self.clientSocket]
        errors = [self.clientSocket]

        # inError: List[socket] = []

        try:
            readReady, writeReady, inError = select.select(inputs, outputs, errors, 0)
        except select.error:
            print("Ethernet Connection Error in select.select")
            return

        if inError:
            print("Ethernet Connection Error")
            return

        while readReady:  # {

            # PyCharm displays if exception here...okay because caught by client code

            data = self.clientSocket.recv(1)

            if data == b'':
                raise SocketBroken("Error 135: Ethernet Socket Connection Broken!")

            self.receiveBuf.append(int.from_bytes(data, byteorder='big'))

            readReady, writeReady, in_error = select.select(inputs, outputs, errors, 0)

        # }

    # EthernetLink::handleReceive
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::connectToRemoteIfRequestPending
    #

        """
            Checks for pending connection requests and accepts one if present. Only one connection at a time is allowed.
            The remote device is expected to initiate the connection.

            If a new connection is accepted, returns 1.
            
            Python also has epoll, poll, and kqueue implementations for platforms that support them. They are more
            efficient versions of select. But perhaps select is more universally supported?
            
            https://stackoverflow.com/questions/5308080/python-socket-accept-nonblocking

            :return: 0 on no new connection, 1 if new connection accepted, -1 on error
            :rtype: int
        """

    def connectToRemoteIfRequestPending(self) -> int:

        if not self.connected:

            readable, writable, error = select.select(self.server_socket_list, [], [], 0)

            if not readable:
                return 0

            for s in readable:

                if s is self.server_socket:

                    self.clientSocket, self.remoteAddress = self.server_socket.accept()
                    self.clientSocketList.append(self.clientSocket)
                    print("\n\nConnection accepted from " + self.remoteDescriptiveName + " at " +
                          self.remoteAddress[0] + "\n")

                    self.connected = True

                    return 1

                # else:
                #
                #     data = s.recv(1024)
                #
                #     if data:
                #         s.send(data)
                #     else:
                #         s.close()
                #         self.client_socket_list.remove(s)

        return 0

    # end of EthernetLink::connectToRemoteIfRequestPending
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getConnected
    #

    def getConnected(self) -> bool:

        """
            Returns the 'connected' flag which is true if connected to remote and false otherwise.
           :return: 'connected' flag
           :rtype: int
        """

        return self.connected

    # end of EthernetLink::getConnected
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::disconnect
    #

    def disconnect(self) -> int:

        """
            Disconnects from the remote device by performing shutdown() and close() on the socket.
            Sets self.connected to False.

            Resets the receive buffer so that any existing data will not affect future operations.

            :return: 0 if successful, -1 on error
            :rtype: int
        """

        self.receiveBuf.reset()

        self.connected = False

        try:
            if self.clientSocket is not None:
                self.clientSocket.shutdown(socket.SHUT_RDWR)
        except OSError:
            print("OSError on socket shutdown...will attempt to close anyway...")
            print("  this is usually OSError: [Errno 107] Transport endpoint is not connected...")
            print("***************************************************************************************")
        try:
            if self.clientSocket is not None:
                self.clientSocket.close()
        except OSError:
            raise SocketBroken("Error 252: Ethernet Socket Connection Broken!")

        print("Disconnected from " + self.remoteDescriptiveName + " at " + self.remoteAddress[0])

        return 0

    # end of EthernetLink::disconnect
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getInputStream
    #

    def getInputStream(self) -> CircularBuffer:

        """
            Returns an "InputStream" for the remote device. For the Python version of this function, actually returns a
            CircularBuffer which the EthernetLink uses to buffer the input stream.
            
            :return: reference to a CircularBuffer used to buffer the input stream for the remote device
            :rtype: CircularBuffer
        """

        return self.receiveBuf

    # end of EthernetLink::getInputStream
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # EthernetLink::getOutputStream
    #

    def getOutputStream(self) -> socket.socket:

        """
            Returns a socket for the remote device. For Python, a socket is returned rather than a Stream as might be
            done for Java (yay Java!).

            :return: reference to a socket for the remote device
            :rtype: socket
        """

        assert self.clientSocket is not None  # see note in this file 'Note regarding Assert' for details

        return self.clientSocket

    # end of EthernetLink::getOutputStream
    # --------------------------------------------------------------------------------------------------


# end of class EthernetLink
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
