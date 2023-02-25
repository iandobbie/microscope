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

"""Raspberry Pi Value Logger module.
"""

import contextlib
import re
import threading
import time
import typing
import logging
import queue
import Adafruit_MCP9808.MCP9808 as MCP9808
#library for TSYS01 sensor
import TSYS01.TSYS01 as TSYS01

import microscope.abc

import RPi.GPIO as GPIO



# Support for async digital IO control on the Raspberryy Pi.
# Currently supports digital input and output via GPIO lines


# Use BCM GPIO references (naming convention for GPIO pins from Broadcom)
# instead of physical pin numbers on the Raspberry Pi board
GPIO.setmode(GPIO.BCM)
_logger = logging.getLogger(__name__)


class RPiValueLogger(microscope.abc.ValueLogger):
    """ValueLogger device for a Raspberry Pi with support for 
    MCP9808 and TSYS01 I2C thermometer chips."""

    def __init__(self, **kwargs):
        super().__init__(numSensors=1, sensors=[],**kwargs)
        # setup io lines 1-n mapped to GPIO lines
        self._sensors = sensors
        for sensor in sensors:
            sensor_type,i2c_address = sensor
                i2c_address=int(i2c_address,0) 
                print ("adding sensor: "+sensor_type +" Adress: %d " % i2c_address)
                if (sensor_type == 'MCP9808'):
                    self.sensors.append(MCP9808.MCP9808(address=i2c_address))
                    #starts the last one added
                    self.sensors[-1].begin()
                    print (self.sensors[-1].readTempC())
                elif (sensor_type == 'TSYS01'):
                    self.sensors.append(TSYS01.TSYS01(address=i2c_address))
                    print (self.sensors[-1].readTempC())


    # functions required as we are DataDevice returning data to the server.
    def _fetch_data(self):
        if (time.time() - self.lastDataTime) > 5.0:
            for i in range(self._numSensors):
                
                self._cache[i]=(19.5+i+5
                                *math.sin(self.lastDataTime/100)
                                +random.random())
                _logger.debug("Sensors %d returns %s" % (i, self._cache[i]))
            self.lastDataTime = time.time()
            print(self._cache)
            return (self._cache)
        return None


    def abort(self):
        pass

    def _do_enable(self):
        return True

    def _do_shutdown(self) -> None:
        pass


    
        #return the list of current temperatures.     
    def get_temperature(self):
        return (self.temperature)

   #function to change updatePeriod
    def tempUpdatePeriod(self,period):
        self.updatePeriod=period

    #function to change readsPerUpdate
    def tempReadsPerUpdate(self,reads):
        self.readsPerUpdate=reads

# needs to be re-written to push data into a queue which _fetch_data can
# then send out to the server. 
        
    #function to read temperature at set update frequency.
    #runs in a separate thread.
    def updateTemps(self):
        """Runs in a separate thread publish status updates."""
        self.temperature = [None] * len(self.sensors)
        tempave = [None] * len(self.sensors)

        self.create_rotating_log()

        if len(self.sensors == 0) :
            return()
        
        while True:
            #zero the new averages.
            for i in xrange(len(self.sensors)):
                tempave[i]=0.0
            #take readsPerUpdate measurements and average to reduce digitisation
            #errors and give better accuracy.
            for i in range(int(self.readsPerUpdate)):
                for i in xrange(len(self.sensors)):
                    try:
                        tempave[i]+=self.sensors[i].readTempC()
                    except:
                        localTemperature=None
                time.sleep(self.updatePeriod/self.readsPerUpdate)
            for i in xrange(len(self.sensors)):    
                self.temperature[i]=tempave[i]/self.readsPerUpdate
                self.logger.info("Temperature-%s =  %s" %(i,self.temperature[i]))
