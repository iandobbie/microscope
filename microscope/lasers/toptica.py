#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright 2016 Mick Phillips (mick.phillips@gmail.com)
# Copyright 2018 David Pinto <david.pinto@bioch.ox.ac.uk>
# Copyright 2019 Ian Dobbie ,ian.dobbie@bioch.ox.ac.uk>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import serial
import re
import Pyro4

from microscope import devices


class TopticaLaser(devices.SerialDeviceMixIn, devices.LaserDevice):
    def __init__(self, com=None, baud=115200, timeout=0.01, **kwargs):
        super(TopticaLaser, self).__init__(**kwargs)
        self.connection = serial.Serial(port = com,
            baudrate = baud, timeout = timeout,
            stopbits = serial.STOPBITS_ONE,
            bytesize = serial.EIGHTBITS, parity = serial.PARITY_NONE)
        # Start a logger.
        response = self.send(b'show serial?')
        self._logger.info("Toptica laser serial number: [%s]", response.decode())

    def send(self, command):
        """Send command and retrieve response."""
        self._write(command)
        response = self._readline()
        # Catch multi-line responses by waiting for prompt.
        while not response.endswith(b'CMD>'):
            response = response + (self._readline())
        return response

    @devices.SerialDeviceMixIn.lock_comms
    def clearFault(self):
        self.send(b'cf')
        return self.get_status()

    @devices.SerialDeviceMixIn.lock_comms
    def is_alive(self):
        response = self.send(b'l?')
        return response in b'01'

    @devices.SerialDeviceMixIn.lock_comms
    def get_status(self):
        result = []
        for function, stat in [(self.get_is_on, 'Emission on?'),
                          (self.get_set_power_mw, 'Target power:'),
                          (self.get_power_mw, 'Measured power:'),
#                          (b'f?', 'Fault?'),
                          (self.get_operating_time, 'Head operating hours:')]:
            response = str(function())
            result.append(stat + " " + response)
        return result

    @devices.SerialDeviceMixIn.lock_comms
    def _on_shutdown(self):
        # Disable laser.
        self.disable()
        self.connection.flushInput()


    ##  Initialization to do when cockpit connects.
    @devices.SerialDeviceMixIn.lock_comms
    def initialize(self):
        self.connection.flushInput()
 

    ## Turn the laser ON. Return True if we succeeded, False otherwise.
    @devices.SerialDeviceMixIn.lock_comms
    def _on_enable(self):
        self._logger.info("Turning laser ON.")
        # Turn on emission.
        response = self.send(b'la on')
        self._logger.info("TopticaLaser: [%s]", response.decode())

        if not self.get_is_on():
            # Something went wrong.
            self._logger.error("Failed to turn on. Current status:\r\n")
            self._logger.error(self.get_status())
            return False
        return True


    ## Turn the laser OFF.
    @devices.SerialDeviceMixIn.lock_comms
    def disable(self):
        self._logger.info("Turning laser OFF.")
        return self.send(b'la off').decode()


    ## Return True if the laser is currently able to produce light.
    @devices.SerialDeviceMixIn.lock_comms
    def get_is_on(self):
        response = self.send(b'status laser')
        return True if (re.findall(b'ON',response)) else False

    def get_min_power_mw(self):
        return 0.0

    @devices.SerialDeviceMixIn.lock_comms
    def get_max_power_mw(self):
        # 'sh data' gets internbal data and max power parsed out
        response = self.send(b'sh data')
        maxPower=float (re.findall(b'Pmax:\s*([0-9.]*)\s*mW',response)[0])
        return maxPower

    @devices.SerialDeviceMixIn.lock_comms
    def get_power_mw(self):
        response = self.send(b'sh power')
        power=int (re.findall(b"PIC\s*=\s*([0-9]*)",response)[0])
        #responce is in uW so /1000.0 to get mW
        return float(power)/1000.0


    @devices.SerialDeviceMixIn.lock_comms
    def _set_power_mw(self, mW):
        ## There is no minimum power on toptica lasers.  Any
        ## non-negative number is accepted.
        self._logger.info("Setting laser power to %.2f mW." % mW)
        return self.send(b'ch 2 power %f' % mW)


    @devices.SerialDeviceMixIn.lock_comms
    def get_set_power_mw(self):
        response = self.send(b'sh level power')
        power=float (re.findall(b'CH2,\s*PWR:\s*([0-9.]*)\s*mW',response)[0])
        return power

    @devices.SerialDeviceMixIn.lock_comms
    def get_operating_time(self):
        response = self.send(b'sh time')
        upTime=int (re.findall(b'LaserUP:\s*([0-9.]*)\s*s',response)[0])/3600
        return upTime
