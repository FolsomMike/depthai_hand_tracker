#!/usr/bin/python3.8 -u

# ----------------------------------------------------------------------------------------------------------------------
#
# circularBuffer.py
# Author: Mike Schoonover
# Date: 07/27/21
#
# Purpose:
#
# This class handles a circular buffer allowing clients to append new data or read data. The buffer is FIFO (first in,
# first out).
#
# Open Source Policy:
#
# This source code is Public Domain and free to any interested party.  Any
# person, company, or organization may do with it as they please.
#
# ----------------------------------------------------------------------------------------------------------------------

import array as arr

from .spudLinkExceptions import NoBytesAvailable

# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
# class CircularBuffer
#
# This class handles a circular buffer.
#


class CircularBuffer:

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::__init__
    #

    def __init__(self, pBufferSize: int):

        """
            CircularBuffer initializer.

            :param pBufferSize: the size of the buffer
            :type pBufferSize: int
        """

        self.bufferSize: int = pBufferSize

        self.buffer = arr.array('i')

        i: int = 0

        while i <= pBufferSize:
            self.buffer.append(0)
            i += 1

        self.nextInsertIndex: int = 0
        self.nextRetrieveIndex: int = 0

    # end of CircularBuffer::__init__
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::reset
    #

    def reset(self) -> int:

        """
            Resets the buffer by setting insert and retrieve pointers to 0. Existing data is not actually cleared from
            the buffer, but resetting the pointers renders any existing data moot.

            :return: always returns 0
            :rtype: int
        """

        self.nextInsertIndex = 0
        self.nextRetrieveIndex = 0

        return 0

    # end of CircularBuffer::reset
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::available
    #

    def available(self) -> int:

        """
            Returns the number of values available for retrieval. This value will never be greater than bufferSize
            even if more data than bufferSize has been appended...once the buffer is full new data will overwrite the
            oldest data.

            :return: number of bytes available for retrieval from the buffer
            :rtype: int
        """

        if self.nextInsertIndex >= self.nextRetrieveIndex:

            return self.nextInsertIndex - self.nextRetrieveIndex

        else:

            return (self.bufferSize - self.nextRetrieveIndex) + self.nextInsertIndex

    # end of CircularBuffer::available
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::append
    #

    def append(self, pValue: int):

        """
            Appends pValue to the end of the data in the buffer. If more values are appended than are read, eventually
            the buffer will overrun and the oldest data will be overwritten by new data. Up to bufferSize number of
            values can be appended without retrieving before an overrun will occur.

            :param pValue: the value to be appended
            :type pValue: int
        """

        self.buffer[self.nextInsertIndex] = pValue

        self.nextInsertIndex += 1

        if self.nextInsertIndex == self.bufferSize:
            self.nextInsertIndex = 0

    # end of CircularBuffer::append
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::retrieve
    #

    def retrieve(self) -> int:

        """
            Retrieves the next available value. If more values are appended than are read, eventually the buffer will
            overrun and the oldest data will be overwritten by new data. Up to bufferSize number of values can be
            appended without retrieving before an overrun will occur.

            :return: the next value available for retrieval
            :rtype: int

            :raises: NoBytesAvailable:  if there are no values available for retrieval

        """

        if self.available() == 0:
            raise NoBytesAvailable

        value = self.buffer[self.nextRetrieveIndex]

        self.nextRetrieveIndex += 1

        if self.nextRetrieveIndex == self.bufferSize:
            self.nextRetrieveIndex = 0

        return value

    # end of CircularBuffer::retrieve
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::read
    #

    def read(self, pBuffer: arr.array, pOffset: int, pNumBytesToRead: int) -> int:

        """
            Retrieves pNumBytesToRead number of values if they are available, storing them in pBuffer starting at index
            pOffset. If less than pNumBytesToRead number of bytes are available, then all available bytes will be
            returned.

            The function returns the number of bytes actually stored in pBuffer.

            If more values are appended than are read, eventually the buffer will overrun and the oldest data will be
            overwritten by new data. Up to bufferSize number of values can be appended without retrieving before an
            overrun will occur.

            :param pBuffer:         buffer in which bytes are to be stored
            :type pBuffer:          arr.array('i')
            :param pOffset:         the index in pBuffer at which the first value is to be stored
            :type pOffset:          int
            :param pNumBytesToRead  the maximum number of bytes to be read
            :return:                the number of bytes read and stored in pBuffer
            :rtype:                 int

        """

        count: int = 0
        i: int = pOffset

        try:

            while count <= pNumBytesToRead:
                pBuffer[i] = self.retrieve()
                count += 1
                i += 1

        except NoBytesAvailable:
            pass

        return i

    # end of CircularBuffer::read
    # --------------------------------------------------------------------------------------------------

    # --------------------------------------------------------------------------------------------------
    # CircularBuffer::peek
    #

    def peek(self) -> int:

        """
            Returns the next available value without removing it from the buffer or adjusting any index pointers.

            :return: the next value available for retrieval
            :rtype: int

            :raises: NoBytesAvailable:  if there are no values available for retrieval

        """

        if self.available() == 0:
            raise NoBytesAvailable

        value = self.buffer[self.nextRetrieveIndex]

        return value

    # end of CircularBuffer::peek
    # --------------------------------------------------------------------------------------------------

# end of class CircularBuffer
# ----------------------------------------------------------------------------------------------------------------------
# ----------------------------------------------------------------------------------------------------------------------
