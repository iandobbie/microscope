#!/usr/bin/env python3

## Copyright (C) 2020 David Miguel Susano Pinto <carandraug@gmail.com>
## Copyright (C) 2023 Ian Dobbie <ian.dobbie@jhu.edu>
##
##
## This file is part of Microscope.
##
## Microscope is free software: you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## Microscope is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Microscope.  If not, see <http://www.gnu.org/licenses/>.

"""Raspberry Pi Digital IO module.
"""

import contextlib
import re
import threading
import time
import typing


import microscope.abc

import RPi.GPIO as GPIO


#Support for async digital IO control on the Raspberryy Pi.
#Currently supports digital input and output via GPIO lines


# Use BCM GPIO references (naming convention for GPIO pins from Broadcom)
# instead of physical pin numbers on the Raspberry Pi board
GPIO.setmode(GPIO.BCM)

class RPiDIO(microscope.abc.DigitalIO):
    '''Digital IO device implementation for a Raspberry Pi

    gpioMap input arrtay maps line numbers to specific GPIO pins
    [GPIO pin, GPIO pin]
    [27,25,29,...]  line 0 in pin 27, 1 is pin 25 etc....'''
    
    def __init__(self,gpioMap = [], **kwargs):
        #setup io lines 1-n mapped to GPIO lines
        self._gpioMap=gpioMap
        self._numLines=len(self._gpioMap)

    #functions needed

    def set_IO_state(self, line: int, state: bool) -> None:
        _logger.info("Line %d set IO state %s"% (line,str(state)))
        if state:
            #true maps to output
            GPIO.setup(self._gpioMap[line],GPIO.OUT)
        else:
            GPIO.setup(self._gpioMap[line],GPIO.IN)

    def get_IO_state(self, line: int) -> bool:
        #returns
        #  True if the line is Output
        #  Flase if Input
        #  None in other cases (i2c, spi etc)
        pinmode=GPIO.gpio_function(self._gpioMap[line])
        if pinmode==GPIO.OUT:
            return True
        elif pinmode==GPIO.IN:
            return False
        return None

    def write_line(self,line: int, state: bool):
        _logger.info("Line %d set IO state %s"% (line,str(state)))
        GPIO.output(self._gpioMap[line],state)
        
    def read_line(self,line: int) -> bool:
        _logger.info("Line %d returns %s" % (line,str(self._cache[line])))
        return GPIO.input(self._gpioMap[line])

    def _do_shutdown(self) -> None:
        pass
