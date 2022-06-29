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

from typing import Final, List, Tuple
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

    def __init__(self, pThisDeviceIdentifier: int):

        self.IN_BUFFER_SIZE: Final[int] = 1024

        self.inBuffer = arr.array('i')

        i: int = 0

        while i <= self.IN_BUFFER_SIZE:
            self.inBuffer.append(0)
            i += 1

        self.OUT_BUFFER_SIZE: Final[int] = 1024

        self.outBuffer = arr.array('B')

        i: int = 0

        while i <= self.OUT_BUFFER_SIZE:
            self.outBuffer.append(0)
            i += 1

        self.thisDeviceIdentifier = pThisDeviceIdentifier

        self.reset()

        self.byteIn: CircularBuffer = type(None)

        self.byteOut: socket = None

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

    def setStreams(self, pInputStream: CircularBuffer, pOutputStream: socket):

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

    def checkForPacketHeaderAvailable(self):

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

        """

        if self.byteIn.available() < 7:
            return

        self.pktChecksum = 0

        if self.byteIn.retrieve() != 0xaa:
            self.resync()
            return

        self.pktChecksum += 0xaa

        if self.byteIn.retrieve() != 0x55:
            self.resync()
            return

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

        self.outBuffer[x] = 0x100 - (checksum & 0xff)
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

        while totalSent < pNumBytesToSend:

            sent = self.byteOut.send(self.outBuffer[totalSent:pNumBytesToSend])
            if sent == 0:
                raise SocketBroken("Error 381: Socket Connection Broken!")
            totalSent = totalSent + sent

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

    def parseUnsignedByteFromPacket(self, pIndex: int) -> (PacketStatusEnum, int, int):

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

    def parseDuplexIntegerFromPacket(self, pIndex: int) -> (PacketStatusEnum, int, int):

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

        if value == copy:
            status: PacketStatusEnum = PacketStatusEnum.PACKET_VALID
        else:
            status: PacketStatusEnum = PacketStatusEnum.DUPLEX_MATCH_ERROR

        return status, pIndex, value

# end of PacketTool::parseDuplexIntegerFromPacket
# --------------------------------------------------------------------------------------------------

#
# //--------------------------------------------------------------------------------------------------
# // PacketTool::sendBytes
# //
# /**
#  * Sends a variable number of bytes (one or more) to the remote device, prepending a valid header
#  * and appending the appropriate checksum.
#  *
#  * Does nothing if comPort not open.
#  *
#  * NOTE: C++ Variadic functions (those with variable number of parameters) force you to use
#  * a variable type of at least size int for the "...". If you try to use char, uint8_t, etc. the
#  * compiler will generate a warning and the code will fail.
#  *
#  * @param pDestAddress		the address of the destination device
#  * @param pPacketType		the packet type
#  * @param pNumBytes			the number of bytes to be sent
#  *							the maximum allowable value is 255; if greater then will be set to 255
#  * @param ...		the list of bytes to be sent; these actually must be ints and cannot be > 255!!!
#  *
#  * @return					true on success, false on failure
#  *
#  */
#
# boolean sendBytes(int pDestAddress, PacketTypeEnum pPacketType, byte... pBytes)
# {
#
# 	if(byteOut == null){ return(false); }
#
# 	int numBytes = pBytes.length;
#
# 	if(numBytes > 255){ numBytes = 255; }
#
# 	int x = prepareHeader(outBuffer, pDestAddress, pPacketType, numBytes);
#
# 	int i;
#
#     for(i=0; i<numBytes; i++){ outBuffer[x++] = pBytes[i]; }
#
# 	int checksum = 0;
#
#     for(int j=0; j<x; j++){ checksum += outBuffer[j]; }
#
#     //calculate checksum and put at end of buffer
#     outBuffer[x++] = (byte)(0x100 - (byte)(checksum & 0xff));
#
#     //send packet to remote
#     if (byteOut != null) {
#         try{
#               byteOut.write(outBuffer, 0 /*offset*/, x);
#               byteOut.flush();
#         }
#         catch (IOException e) {
#             logSevere(e.getMessage() + " - Error: 422");
# 			return(false);
#         }
#     }
#
# 	return(true);
#
# }//end of PacketTool::sendBytes
# //--------------------------------------------------------------------------------------------------
#
# //--------------------------------------------------------------------------------------------------
# // PacketTool::sendIntegersPacket
# //
#  /**
#  *
#  * Sends a variable number of two-byte signed integers to the remote device, prepending a valid
#  * header and appending the appropriate checksum.
#  *
#  * All integers must be -32768<value<32767 or function will return with error.
#  *
#  * The integers are sent using Big Endian order (MSB first).
#  *
#  * If pDuplexMode is true, each integer will be sent twice to allow for verification by the
#  * receiver. Each integer will be immediately followed by a copy of the integer.
#  *
#  * Does nothing if comPort not open.
#  *
#  * @param pDestAddress		the address of the destination device
#  * @param pPacketType		the packet type
#  * @param pDuplexMode		if true then each value will be sent twice
#  * @param pValues			the values to be sent; each must be -32768<value<32767; the maximum
#  *							number of values which can be sent is 127 if pDuplexMode = false
#  *							and 63 if pDuplexMode = true
#  *
#  * @return					true on success; false on send failure or if any value is out of
#  *							range or if too many values specified
#  *
#  */
#
# boolean sendIntegersPacket(int pDestAddress, PacketTypeEnum pPacketType, boolean pDuplexMode,
# 																				 int... pValues)
# {
#
# 	if(byteOut == null){ return(false); }
#
# 	int numValues = pValues.length;
#
# 	byte [] buf = null;
#
# 	if(!pDuplexMode){
# 		if(numValues > 127){ return(false); }
# 		buf = new byte[numValues * 2];
# 	}
#
# 	if(pDuplexMode){
# 		if(numValues > 63){ return(false); }
# 		buf = new byte[numValues * 4];
# 	}
#
# 	int x = 0;
#
# 	for(int i=0; i<numValues; i++){
#
# 		buf[x++] = (byte) ((pValues[i] >> 8) & 0xff);
# 		buf[x++] = (byte) (pValues[i] & 0xff);
#
# 		if(pDuplexMode){
# 			buf[x++] = (byte) ((pValues[i] >> 8) & 0xff);
# 			buf[x++] = (byte) (pValues[i] & 0xff);
# 		}
#
# 	}
#
# 	boolean status = sendBytes(pDestAddress, pPacketType, buf);
#
# 	return(status);
#
# }//end of PacketTool::sendIntegersPacket
# //--------------------------------------------------------------------------------------------------
#
# //--------------------------------------------------------------------------------------------------
# // PacketTool::sendDuplexIntegersPacket
# //
#  /**
#  * Convenience method to call sendIntegersPacket with pDuplexMode set true.
#  *
#  * Sends a variable number of two-byte signed integers to the remote device, prepending a valid
#  * header and appending the appropriate checksum.
#  *
#  * All integers must be -32768<value<32767 or function will return with error.
#  *
#  * The integers are sent using Big Endian order (MSB first).
#  *
#  * Each integer will be sent twice to allow for verification by the receiver. Each integer will be
#  * immediately followed by a copy of the integer.
#  *
#  * Does nothing if comPort not open.
#  *
#  * @param pDestAddress		the address of the destination device
#  * @param pPacketType		the packet type
#  * @param pValues			the values to be sent; each must be -32768<value<32767; the maximum
#  *							number of values which can be sent is 127 if pDuplexMode = false
#  *							and 63 if pDuplexMode = true
#  *
#  * @return					true on success; false on send failure or if any value is out of
#  *							range or if too many values specified
#  *
#  */
#
# boolean sendDuplexIntegersPacket(int pDestAddress, PacketTypeEnum pPacketType, int... pValues)
# {
#
# 	boolean status = sendIntegersPacket(pDestAddress, pPacketType, true, pValues);
#
# 	return(status);
#
# }//end of PacketTool::sendDuplexIntegersPacket
# //--------------------------------------------------------------------------------------------------
#
# //--------------------------------------------------------------------------------------------------
# // PacketTool::waitForNumberOfBytes
# //
# /**
#  * Waits until pNumBytes number of data bytes are available in the socket or until the specified
#  * number of milliseconds pTimeOutMillis has passed.
#  *
#  * @param pNumBytes			the number of bytes to wait for
#  * @param pTimeOutMillis	the maximum number of milliseconds to wait
#  * @return					the number of bytes available or -1 if time out occurred or com error
#  *
#  */
#
# int PacketTool(int pNumBytes, int pTimeOutMillis)
# {
#
# 	long startTime = System.currentTimeMillis();
#
# 	try{
# 		while((System.currentTimeMillis() - startTime) < pTimeOutMillis){
# 			if (byteIn.available() >= pNumBytes) {return(byteIn.available());}
# 		}
# 	}catch (IOException e) {
# 		logSevere(e.getMessage() + " - Error: 528");
# 		return(-1);
#     }
#
# 	return(-1);
#
# }//end of PacketTool::waitForNumberOfBytes
# //--------------------------------------------------------------------------------------------------
#
# //--------------------------------------------------------------------------------------------------
# // PacketTool::readBytes
# //
# /**
#  * Retrieves pNumBytes number of data bytes from the stream and stores them in inBuffer.
#  * Returns the number of characters placed in the buffer. A 0 means no valid data was found.
#  * Will timeout based on previous call to setTimeout(SERIAL_TIMEOUT_MILLIS).
#  *
#  * @param pNumBytes	number of bytes to read
#  * @return			number of bytes retrieved from the socket; if the attempt times out returns 0
#  *
#  */
#
# int readBytes(int pNumBytes)
# {
#
# 	try{
# 		return(byteIn.read(inBuffer, 0, pNumBytes));
# 	} catch (IOException e) {
# 		logSevere(e.getMessage() + " - Error: 556");
# 		return(0);
#     }
#
# }//end of PacketTool::readBytes
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::processDataPackets
# //
# // The amount of time the function is to wait for a packet is specified by
# // pTimeOut.  Each count of pTimeOut equals 10 ms.
# //
# // See processOneDataPacket notes for more info.
# //
#
# public int processDataPackets(boolean pWaitForPkt, int pTimeOut)
# {
#
#     int x = 0;
#
#     //process packets until there is no more data available
#
#     // if pWaitForPkt is true, only call once or an infinite loop will occur
#     // because the subsequent call will still have the flag set but no data
#     // will ever be coming because this same thread which is now blocked is
#     // sometimes the one requesting data
#
#     //wip mks -- is the above true? explain better or change the functionality
#
#     if (pWaitForPkt) {
#         return processOneDataPacket(pWaitForPkt, pTimeOut);
#     }
#     else {
#         while ((x = processOneDataPacket(pWaitForPkt, pTimeOut)) != -1){}
#     }
#
#     return x;
#
# }//end of PacketTool::processDataPackets
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::processOneDataPacket
# //
# // This function processes a single data packet if it is available.  If
# // pWaitForPkt is true, the function will wait until data is available.
# //
# // This function should be overridden by sub-classes to provide specialized
# // functionality.
# //
#
# public int processOneDataPacket(boolean pWaitForPkt, int pTimeOut)
# {
#
#     return(0);
#
# }//end of PacketTool::processOneDataPacket
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::waitSleep
# //
# // Sleeps for pTime milliseconds.
# //
#
# public void waitSleep(int pTime)
# {
#
#     try {Thread.sleep(pTime);} catch (InterruptedException e) { }
#
# }//end of PacketTool::waitSleep
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::logStatus
# //
# // Writes various status and error messages to the log window.
# //
#
# public void logStatus(ThreadSafeLogger pLogger)
# {
#
# }//end of PacketTool::logStatus
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::logSevere
# //
# // Logs pMessage with level SEVERE using the Java logger.
# //
#
# void logSevere(String pMessage)
# {
#
#     Logger.getLogger(getClass().getName()).log(Level.SEVERE, pMessage);
#
# }//end of PacketTool::logSevere
# //-----------------------------------------------------------------------------
#
# //-----------------------------------------------------------------------------
# // PacketTool::logStackTrace
# //
# // Logs stack trace info for exception pE with pMessage at level SEVERE using
# // the Java logger.
# //
#
# void logStackTrace(String pMessage, Exception pE)
# {
#
#     Logger.getLogger(getClass().getName()).log(Level.SEVERE, pMessage, pE);
#
# }//end of PacketTool::logStackTrace
# //-----------------------------------------------------------------------------
#

# end of class PacketTool
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
