#!/usr/bin/python3.8 -u

# ----------------------------------------------------------------------------------------------------------------------
#
# packetTool.py
# Author: Mike Schoonover
# Date: 07/04/21
#
# Purpose:
#
# Handles formatting, verification, reading, and writing of packets.
#
# ----------------------------------------------------------------------------------------------------------------------

from typing import Final, Tuple, List, Optional
import array as arr
import socket

from .spudLinkExceptions import SocketBroken
from .packetTypeEnum import PacketTypeEnum
from .packetStatusEnum import PacketStatusEnum
from .circularBuffer import CircularBuffer

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# class PacketTool
#
# This class handles formatting, verification, reading, and writing of packets.
#


class PacketTool:

    # --------------------------------------------------------------------------------------------------
    # PacketTool::__init__
    #

    """
        Note regarding Assert:

            Mypy is STUPID. When a reference is declared like 'self.byteOut: Optional[socket] = None'
            then Mypy sometimes complains later (but NOT always!!!) with:

                Item "None" of Optional[] has no attribute

            To shut up the warning, assert that the variable is not None before using it in that method:

                assert self.byteOut is not None

            Sometimes required, sometimes not...yet another mystery of Python and Mypy.

    """

    def __init__(self, pThisDeviceIdentifier: int):

        self.IN_BUFFER_SIZE: Final[int] = 1024

        self.inBuffer = arr.array('i')

        i: int = 0

        while i <= self.IN_BUFFER_SIZE:
            self.inBuffer.append(0)
            i += 1

        self.OUT_BUFFER_SIZE: Final[int] = 1024

        self.outBuffer = arr.array('B')

        i = 0

        while i <= self.OUT_BUFFER_SIZE:
            self.outBuffer.append(0)
            i += 1

        self.thisDeviceIdentifier = pThisDeviceIdentifier

        self.reset()

        self.byteIn: Optional[CircularBuffer] = None

        self.byteOut: Optional[socket.socket] = None

        self.TIMEOUT: Final[int] = 50
        self.timeOutProcess: int = 0      # use this one in the packet process functions

        # the following section's functionality duplicated in reset() function

        self.pktType: PacketTypeEnum = PacketTypeEnum.NO_PKT

        self.headerValid: bool = False

        self.numPktDataBytes: int = 0

        self.numDataBytesPlusChecksumByte: int = 0

        self.pktChecksum: int = 0

        self.destDeviceIdentifierFromReceivedPkt: int = 0

        self.sourceDeviceIdentifierFromReceivedPkt: int = 0

        self.resyncCount: int = 0

        self.reSynced: bool = False

        self.reSyncCount: int = 0

        self.reSyncSkip: int = 0

        self.reSyncPktID: int = 0

    # end of PacketTool::__init__
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::setStreams
    #

    def setStreams(self, pInputStream: CircularBuffer, pOutputStream: socket.socket):

        """
            Sets the input and output streams for the communication port.

            For the Python version of this function:

                pInputStream actually accepts a CircularBuffer which the EthernetLink uses to buffer the input stream.

                pOutputStream accepts a socket instead of some type of stream as might be done for Java (yay Java!)

            :param pInputStream:	InputStream for the communications port...actually a CircularBuffer in the Python
                                    version of this function
            :type pInputStream:     CircularBuffer
            :param pOutputStream:	OutputStream for the communications port
            :type pOutputStream:    socket

        """

        self.byteIn = pInputStream
        self.byteOut = pOutputStream

    # end of PacketTool::setStreams
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::reset
    #

    def reset(self):

        """
            Resets all flags and variables. This dumps any partial packet header or data already read and prepares
            to collect new packets.

        """

        self.pktType = PacketTypeEnum.NO_PKT

        self.headerValid = False

        self.numPktDataBytes = 0

        self.numDataBytesPlusChecksumByte = 0

        self.pktChecksum = 0

        self.destDeviceIdentifierFromReceivedPkt = 0

        self.sourceDeviceIdentifierFromReceivedPkt = 0

        self.resyncCount = 0

        self.reSynced = False

        self.reSyncCount = 0

        self.reSyncSkip = 0

        self.reSyncPktID = 0

    # end of PacketTool::reset
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::getPktType
    #

    def getPktType(self) -> PacketTypeEnum:

        """
            Returns the packet type code of the last received packet.

            :return:    the packet type code of the last received packet
            :rtype:     PacketTypeEnum

        """

        return self.pktType

    # end of PacketTool::getPktType
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::checkForPacketReady
    #

    def checkForPacketReady(self) -> bool:

        """
            Checks to see if a full packet has been received. Returns true if a complete packet has been
            received, the checksum is valid, and the packet is addressed to this device (host computer).

            If ready, the packet type can be accessed by calling getPktType(). The number of data bytes in
            the packet can be retrieved by calling getNumPktDataBytes(). The data bytes buffer can be
            accessed by calling getPktDataBuffer().

            If the checksum for a packet is invalid, function will return false.

            If the function returns false for any reason the state of the pktType, packet data buffer,
            and numPktDataBytes are undefined in that case.

            If enough bytes are waiting in the receive buffer to form a packet header, those bytes are
            retrieved and the header is analyzed. If enough bytes are waiting in the receive buffer to
            complete the entire packet based on the number of data bytes specified in the header, those
            bytes are retrieved and this function returns true if the checksum is valid.

            If a packet header can be read but the full packet is not yet available, the header info is
            stored for use in succeeding calls which will keep checking for enough bytes to complete the
            packet. The function will return false until the full packet has been read.

            If 0xaa,0x55 is not found when the start of a header is expected, the buffer will be stripped of
            bytes until it is empty or 0xaa is found. The stripped bytes will be lost forever.

            NOTE		This function should be called often to prevent serial buffer overflow!

            :return:    true if a full packet with valid checksum is ready, false otherwise
            :rtype:     bool

        """

        if self.byteIn is None:
            return False

        if not self.headerValid:
            self.checkForPacketHeaderAvailable()
            if not self.headerValid:
                return False

        numBytesAvailable: int = self.byteIn.available()

        if numBytesAvailable < self.numDataBytesPlusChecksumByte:
            return False

        self.headerValid = False     # reset for next header search since this one is now handled

        self.byteIn.read(self.inBuffer, 0, self.numDataBytesPlusChecksumByte)

        if self.destDeviceIdentifierFromReceivedPkt != self.thisDeviceIdentifier:
            return False

        i: int = 0
        while i < self.numDataBytesPlusChecksumByte:
            self.pktChecksum += self.inBuffer[i]
            i += 1

        if self.pktChecksum & 0xff != 0:
            return False

        return True

    # end of PacketTool::checkForPacketReady
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::checkForPacketHeaderAvailable
    #

    def checkForPacketHeaderAvailable(self) -> int:

        """
            Checks to see if a header is available in the com buffer. At least 6 bytes must be available
            and the first two bytes must b 0xaa,0x55.

            If a valid header is found, other functions can detect this state by checking if
            (headerValid == true).

            If a valid header is found, destDeviceIdentifierFromReceivedPkt, sourceDeviceIdentifierFromReceivedPkt,
            pktType, and numPktDataBytes will be set to the values specified in the header. The bytes in the
            header will be summed and stored in pktCheckSum.

            The numPktDataBytes value retrieved from the packet is a 16 bit unsigned integer. Python does not have
            unsigned values, but the 16 bit unsigned value fits into a Python integer as an always-positive number.

            For convenience, numDataBytesPlusChecksumByte will be set to (numPktDataBytes + 1).

            If 0xaa,0x55 is not found when the start of a header is expected, the buffer will be stripped of
            bytes until it is empty or 0xaa is found. The stripped bytes will be lost forever. The next
            call to checkForPacketReady will then attempt to read the header or toss more bytes if
            more invalid data has been received by then.

            There is no way to verify the header until the entire packet is read. The packet checksum
            includes the header, so at that time the entire packet can be validated or tossed.

            :return: always returns 0
            :rtype: int
        """

        assert self.byteIn is not None

        if self.byteIn.available() < 7:
            return 0

        self.pktChecksum = 0

        if self.byteIn.retrieve() != 0xaa:
            self.resync()
            return 0

        self.pktChecksum += 0xaa

        if self.byteIn.retrieve() != 0x55:
            self.resync()
            return 0

        self.pktChecksum += 0x55

        self.destDeviceIdentifierFromReceivedPkt = self.byteIn.retrieve()

        self.pktChecksum += self.destDeviceIdentifierFromReceivedPkt

        self.sourceDeviceIdentifierFromReceivedPkt = self.byteIn.retrieve()

        self.pktChecksum += self.sourceDeviceIdentifierFromReceivedPkt

        pktTypeInt: int = self.byteIn.retrieve()

        self.pktChecksum += pktTypeInt

        self.pktType = PacketTypeEnum(pktTypeInt)

        numPktDataBytesMSB: int = self.byteIn.retrieve()

        self.pktChecksum += numPktDataBytesMSB

        numPktDataBytesLSB: int = self.byteIn.retrieve()

        self.pktChecksum += numPktDataBytesLSB

        self.numPktDataBytes = (((numPktDataBytesMSB << 8) & 0xff00) + (numPktDataBytesLSB & 0xff))

        self.numDataBytesPlusChecksumByte = self.numPktDataBytes + 1

        self.headerValid = True

        return 0

    # end of PacketTool::checkForPacketHeaderAvailable
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::resync
    #

    def resync(self):

        """
            Reads and tosses bytes from byteIn until 0xaa is found or the buffer is empty. If found, the
            0xaa byte is left in the buffer to be read by the next attempt to read the header.

            Increments resyncCount.
        """

        self.resyncCount += 1

        while self.byteIn.available() > 0:
            if self.peekForValue(0xaa):
                return

    # end of PacketTool::resync
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::peekForValue
    #

    def peekForValue(self, pTargetValue: int) -> bool:

        """
            Peeks at the next value in byteIn and reads and tosses it if it doesn't match pTargetValue.

            If the peeked at value matches pTargetValue it is left in the buffer and will again be available for
            reading or peeking; method returns true.

            If the peeked at value does not match pTargetValue the byte is read and tossed; method returns false.

            :param pTargetValue:	the value to match with the next byte in byteIn
            :type pTargetValue:     int
            :return:    true if the next value in byteIn matches pTargetValue, false otherwise
            :rtype:     bool
         """

        assert self.byteIn is not None  # see note in this file 'Note regarding Assert' for details

        peekVal: int = self.byteIn.peek()

        if peekVal != pTargetValue:
            self.byteIn.retrieve()
            return False
        else:
            return True

    # end of PacketTool::peekForValue
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::prepareHeader
    #

    def prepareHeader(self, pDestAddress: int, pPacketType: PacketTypeEnum, pNumDataBytes: int) -> int:

        """
            Sets up a valid packet header at the beginning of self.outBuffer. The header includes:

            0xaa, 0x55, <dest device identifier>, <this device identifier>, <packet type>,
                             <number of data bytes in packet (MSB)> <number of data bytes in packet (LSB)>

            If the number of data bytes is unknown when this method is called, pNumDataBytes can be set to any
            number and the client code can later invoke setPacketNumDataBytes method when the value is known but
            before the checksum is calculated.

            The number of data bytes excludes this header and the checksum. Example full packet:

            0xaa, 0x55, 1, 0, 1, 4, 5, 1, 2, 3, 4, 0x??

            where:
                0xaa, 0x55 are identifier bytes used in all packet headers
                1 is the destination device's identifier (1 for Backpack Device)
                0 is this device's identifier (0 for HOST computer)
                1 is the packet type (will vary based on the type of packet)
                4 is the number of data bytes ~ upper byte of int
                5 is the number of data bytes ~ lower byte of int
                1,2,3,4 are the data bytes
                0x?? is the checksum for all preceding header and data bytes

          Note that this function only sets up the header in the buffer, the data bytes and checksum must
          be added by the calling function.

        :param pDestAddress:	the identifier of the destination device
        :type pDestAddress:     int
        :param pPacketType:	    the packet type
        :type pPacketType:      PacketTypeEnum
        :param pNumDataBytes:	the number of data bytes that will later be added to the packet by client code
        :type pNumDataBytes:    int

        :return:                the number of values added to the buffer; the index of next empty spot
        :rtype:                 int

        """

        x: int = 0

        self.outBuffer[x] = 0xaa
        x += 1

        self.outBuffer[x] = 0x55
        x += 1

        self.outBuffer[x] = pDestAddress
        x += 1

        self.outBuffer[x] = self.thisDeviceIdentifier
        x += 1

        self.outBuffer[x] = pPacketType.value
        x += 1

        self.outBuffer[x] = ((pNumDataBytes >> 8) & 0xff)
        x += 1

        self.outBuffer[x] = (pNumDataBytes & 0xff)
        x += 1

        return x

    # end of PacketTool::prepareHeader
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::calculateChecksumAndStoreInBuffer
    #

    def calculateChecksumAndStoreInBuffer(self, pLastIndex: int) -> int:

        """
            Calculates the checksum for all bytes in self.outBuffer from index 0 up to but excluding index pLastIndex.
            The checksum is then stored in the buffer at pLastIndex.

            Returns pLastIndex + 1, which is the number of bytes in the packet including the header, data bytes, and
            checksum.

        :param pLastIndex:	the index position immediately after the checksum - this is also the packet size in bytes
        :type pLastIndex:   int

        """

        checksum: int = 0

        x: int = pLastIndex

        j: int = 0
        while j < x:
            checksum += self.outBuffer[j]
            j += 1

        # calculate checksum and put at end of buffer

        try:
            self.outBuffer[x] = 0x100 - (checksum & 0xff)
        except OverflowError:
            print("Checksum: ", checksum)

        x += 1

        return pLastIndex + 1

    # end of PacketTool::calculateChecksumAndStoreInBuffer
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::setPacketNumDataBytes
    #

    def setPacketNumDataBytes(self, pNumDataBytes: int):

        """
            Stores 16 least significant bits of pNumDataBytes in outBuffer at the proper location in a header for
            the number-of-data-bytes value.

            The integer is stored using Big Endian order (MSB first).

            If the number of data bytes is unknown when prepareHeader method is called, pNumDataBytes can be set to any
            number for that call and the client code can later invoke this method when the value is known but
            before the checksum is calculated.

        :param pNumDataBytes:	the number of data bytes that will later be added to the packet by client code
        :type pNumDataBytes:    int

        """

        x: int = 5

        self.outBuffer[x] = ((pNumDataBytes >> 8) & 0xff)
        x += 1

        self.outBuffer[x] = (pNumDataBytes & 0xff)
        x += 1

    # end of PacketTool::setPacketNumDataBytes
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::sendOutBuffer
    #

    def sendOutBuffer(self, pNumBytesToSend: int) -> bool:

        """
             Sends the data in self.outBuffer to the remote device. No additional preparation is performed on the data.

            :param pNumBytesToSend: the number of bytes in the buffer to be sent
            :type pNumBytesToSend:  int

            :return:            true if no error, false on error
            :rtype:             bool

            :raises: SocketBroken:  if the socket is closed or becomes inoperable

         """

        totalSent: int = 0

        assert self.byteOut is not None    # see note in this file 'Note regarding Assert' for details

        while totalSent < pNumBytesToSend:

            sent = self.byteOut.send(self.outBuffer[totalSent:pNumBytesToSend].tobytes())

            if sent == 0:
                raise SocketBroken("Error 381: Socket Connection Broken!")
            totalSent += sent

        return True

    # end of PacketTool::sendOutBuffer
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::sendString
    #

    def sendString(self, pDestAddress: int, pPacketType: PacketTypeEnum, pString: str) -> bool:

        """
            Sends a string (Python str) to the remote device, prepending a valid header and appending the appropriate
            checksum. A null terminator (0x00) will be added to the end of the string.

            If the string plus a null terminator along with the header and checksum will not fit into the output
            buffer, the string will be truncated as required

            :param pDestAddress: the address of the remote device
            :type pDestAddress:  int
            :param pPacketType: the packet type code
            :type pPacketType:  PacketTypeEnum
            :param pString:     the string to send
            :type pString:      str
            :return:            true if no error, false on error
            :rtype:             bool

            :raises: SocketBroken:  if the socket is closed or becomes inoperable

         """

        msgBytes: bytes = str.encode(pString)

        msgLength: int = len(msgBytes)

        msgLengthPlusNullTerminator: int = msgLength + 1

        x: int = self.prepareHeader(pDestAddress, pPacketType, msgLengthPlusNullTerminator)

        i: int = 0

        while i < msgLength:
            self.outBuffer[x] = msgBytes[i]
            i += 1
            x += 1
            if x == self.OUT_BUFFER_SIZE - 2:
                break

        # add null terminator at end of string
        if x < (self.OUT_BUFFER_SIZE - 1):
            self.outBuffer[x] = 0
            x += 1

        x = self.calculateChecksumAndStoreInBuffer(x)

        return self.sendOutBuffer(x)

    # end of PacketTool::sendString
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::sendSignedShortIntsFromListOfTuples
    #

    def sendSignedShortIntsFromListOfTuples(self, pDestAddress: int, pPacketType: PacketTypeEnum,
                                            pData: List[Tuple[int, ...]]) -> bool:

        """
            Sends a series of signed short ints (16 bits sent as 2 bytes each) to the remote device, prepending a
            valid header and appending the appropriate checksum.

            The short ints will be read from a List of Tuples. The List can contain unlimited Tuples and each Tuple
            can contain unlimited ints. Only the two least significant bytes of each Python int will be sent.

            The values are sent Big Endian.

            If the byte series along with the header and checksum will not fit into the output buffer, the series
            will be truncated as required

            :param pDestAddress: the address of the remote device
            :type pDestAddress:  int
            :param pPacketType: the packet type code
            :type pPacketType:  PacketTypeEnum
            :param pData:       the List of Tuples containing ints of which the two least significant bytes of each
                                are to be sent
            :type pData:        List[Tuple[int]]
            :return:            true if no error, false on error
            :rtype:             bool

            :raises: SocketBroken:  if the socket is closed or becomes inoperable

         """

        numBytes: int = 1

        # actual number of data bytes is unknown, so any value in numBytes works for now - will be updated later

        x: int = self.prepareHeader(pDestAddress, pPacketType, numBytes)

        numDataBytes: int = 0

        for aTuple in pData:
            for anInt in aTuple:

                self.outBuffer[x] = (anInt >> 8) & 0xff
                x += 1
                numDataBytes += 1

                if x == self.OUT_BUFFER_SIZE - 1:
                    break

                self.outBuffer[x] = anInt & 0xff
                x += 1
                numDataBytes += 1

                if x == self.OUT_BUFFER_SIZE - 1:
                    break

        self.setPacketNumDataBytes(numDataBytes)

        x = self.calculateChecksumAndStoreInBuffer(x)

        return self.sendOutBuffer(x)

    # end of PacketTool::sendSignedShortIntsFromListOfTuples
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::signExtend
    #

    @staticmethod
    def signExtend(pValue: int, pBits: int) -> int:

        """
            Perform sign extension operation on pValue. The parameter pBits specifies the number of relevant bits in
            pValue. If the MSB of these bits is 1 then pValue is negative; all bits above that will be set to 1 to make
            the return value negative.

            Thus if the incoming value is a signed 16 bit value, pBits should equal 16.

            The returned integer will be sign-extended all the way to the top bit regardless of the bit size of the
            integer, the size of which may vary in future Python versions.

            :param pValue:     the value to be sign-extended
            :type pValue:      int
            :param pBits:      the number of relevant bits in pValue which contain the actual value
            :type pBits:       int
            :return:           value with the sign bit at bit position pBits-1 extended through to the integer's top bit
            :rtype:            int
        """

        signBit = 1 << (pBits - 1)
        mask = signBit - 1
        return (pValue & mask) - (pValue & signBit)

    # end of PacketTool::signExtend
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::parseUnsignedByteFromPacket
    #

    def parseUnsignedByteFromPacket(self, pIndex: int) -> Tuple[PacketStatusEnum, int, int]:

        """

             Extracts a single unsigned byte from the current packet data in self.inBuffer starting at position pIndex
             in the array. The byte is returned as an int in order to handle the full range of an unsigned byte.

            The index value is adjusted and returned such that it points to the next buffer position after the
            value and its copy which has just been parsed. Thus the index will point to the next data element and
            can be used in a subsequent call to parse such an element.

            :param pIndex:      the index of the MSB of the integer to be parsed from the buffer
            :type pIndex:       int
            :return:            the packet parsing status, the updated index, the byte value extracted (as an int)
                                the status will be:
                                    PacketStatusEnum::PACKET_VALID if no error
                                    PacketStatusEnum::DUPLEX_MATCH_ERROR if the two copies in the packet of the
                                     value do not match
                                the index returned will point to the position after the value and its copy
            :rtype:             PacketStatusEnum, int, int

        """

        value: int = self.inBuffer[pIndex]
        pIndex += 1

        value = self.signExtend(value, 8)

        status: PacketStatusEnum = PacketStatusEnum.PACKET_VALID

        return status, pIndex, value

    # end of PacketTool::parseUnsignedByteFromPacket
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # PacketTool::parseIntegerFromDuplexPacket
    #

    def parseDuplexIntegerFromPacket(self, pIndex: int) -> Tuple[PacketStatusEnum, int, int]:

        """
 
             Extracts a two-byte signed integer from the current packet data in self.inBuffer starting at position
             pIndex in the array. The integer is reconstructed from the two data bytes at that index
             position.
             
            The integer is parsed using Big Endian order (MSB first).
             
            The value's copy is also extracted from the buffer immediately after the value itself. The two
            are compared to verify integrity.

            The index value is adjusted and returned such that it points to the next buffer position after the
            value and its copy which has just been parsed. Thus the index will point to the next data element and
            can be used in a subsequent call to parse such an element.

            :param pIndex:      the index of the MSB of the integer to be parsed from the buffer
            :type pIndex:       int
            :return:            the packet parsing status, the updated index, the int value extracted
                                the status will be:
                                    PacketStatusEnum::PACKET_VALID if no error
                                    PacketStatusEnum::DUPLEX_MATCH_ERROR if the two copies in the packet of the
                                     value do not match
                                the index returned will point to the position after the value and its copy
            :rtype:             PacketStatusEnum, int, int

        """

        valueMSB: int = self.inBuffer[pIndex]
        pIndex += 1

        valueLSB: int = self.inBuffer[pIndex]
        pIndex += 1

        value: int = (((valueMSB << 8) & 0xff00) + (valueLSB & 0xff))

        value = self.signExtend(value, 16)

        copyMSB: int = self.inBuffer[pIndex]
        pIndex += 1

        copyLSB: int = self.inBuffer[pIndex]
        pIndex += 1

        copy: int = (((copyMSB << 8) & 0xff00) + (copyLSB & 0xff))

        copy = self.signExtend(copy, 16)

        status: PacketStatusEnum

        if value == copy:
            status = PacketStatusEnum.PACKET_VALID
        else:
            status = PacketStatusEnum.DUPLEX_MATCH_ERROR

        return status, pIndex, value

# end of PacketTool::parseDuplexIntegerFromPacket
# --------------------------------------------------------------------------------------------------

# end of class PacketTool
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
