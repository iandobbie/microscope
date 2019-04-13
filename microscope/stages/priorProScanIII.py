#!/usr/bin/python
# -*- coding: utf-8
#
# Copyright 2019 Ian Dobbie (Ian.Dobbie@gmail.com)
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


#still to implement
#get position per axis
#getmovement time
#set speed and accelleration
#cleanupupafterexperiment function?



import serial

import Pyro4

from microscope import devices


@Pyro4.expose
class PriorProScanIII( devices.SerialDeviceMixIn, devices.StageDevice):

    def __init__(self, com=None, baud=9600, timeout=0.1, *args, **kwargs):
        # default baufd rate is 9600
        # no parity or flow control
        # timeout is recomended to be over 0.5
        super(PriorProScanIII, self).__init__(*args, **kwargs)
        self.connection = serial.Serial(port = com,
            baudrate = baud, timeout = timeout,
            stopbits = serial.STOPBITS_ONE,
            bytesize = serial.EIGHTBITS, parity = serial.PARITY_NONE)
        #check axis encoder states.
        self.encoderState=self._encoder_state()
        #turn on encoders if needed and set servo mode off
        for axis in self.encoderState:
            if not self.encoderState[axis]:
                self.send(b'ENCODER,'+axis+',1')
            
        #turn off servo mode by default
        self.send(b'SERVO,b,0')
        
            

    def _write(self, command):
        """Send a command to the prior device.

        This is not a simple passthrough to ``serial.Serial.write``,
        it will append ``b'\\r'`` to command.  This overides the
        defualt write method
        """
        return self.connection.write(command + b'\r')

    def send(self, command):
        """Send command and retrieve response."""
        self._write(command)
        return self._readline()

#    @devices.SerialDeviceMixIn.lock_comms
#    def clearFault(self):
#        self.flush_buffer()
#        return self.get_status()

    def flush_buffer(self):
        line = b' '
        while len(line) > 0:
            line = self._readline()

    @devices.SerialDeviceMixIn.lock_comms
    def get_status(self):
        result = self.send(b'?')
        return result.split(b'\r')
    

    @devices.SerialDeviceMixIn.lock_comms
    def get_position(self):
        result = self.send(b'P').split(b',')
        return ([int(result[0]),int(result[1])])

    @devices.SerialDeviceMixIn.lock_comms
    def stop(self):
        self.send(b'I')

    @devices.SerialDeviceMixIn.lock_comms
    def move_abs(self,pos):
        position="%f,%f"%(pos[0],pos[1])
        self.send(b'G,'+position.encode())
        #move returns a responce
        self._readline()
        
    @devices.SerialDeviceMixIn.lock_comms
    def move_relative(self,pos):
        position="%f,%f"%(pos[0],pos[1])
        responce=self.send(b'GR,'+position.encode())
        #move returns a responce
        if(responce==b'R\r'):
            return
        else:
            #something went wrong
            pass

    @devices.SerialDeviceMixIn.lock_comms
    def get_serialnumber(self):
        return(self.send(b'SERIAL').strip(b'\r'))

    
    @devices.SerialDeviceMixIn.lock_comms
    def home(self):
        self.send(b'RIS')

        
    @devices.SerialDeviceMixIn.lock_comms
    def _encoder_state(self):
        encoderState=int(self.send(b'ENCODER'))
        responce= {'X':  True if (encoderState & 1) else False ,
                   'Y': True if (encoderState & 2) else False }
        return (responce)
