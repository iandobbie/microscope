#!/usr/bin/env python3

## Copyright (C) 2020 David Miguel Susano Pinto <carandraug@gmail.com>
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

import ctypes
import warnings

import numpy
import weakref
import typing

import microscope
import microscope.abc


try:
    import microscope._wrappers.asdk as asdk
except Exception as e:
    raise microscope.LibraryLoadError(e) from e


class AlpaoDeformableMirror(microscope.abc.DeformableMirror, microscope.abc.Stage):
    """Alpao deformable mirror.

    The Alpao mirrors support hardware triggers modes
    `TriggerMode.ONCE` and `TriggerMode.START`.  By default, they will
    be set for software triggering, and trigger once.

    Args:
        serial_number: the serial number of the deformable mirror,
            something like `"BIL103"`.
    """

    _TriggerType_to_asdkTriggerIn = {
        microscope.TriggerType.SOFTWARE: 0,
        microscope.TriggerType.RISING_EDGE: 1,
        microscope.TriggerType.FALLING_EDGE: 2,
    }

    _supported_TriggerModes = [
        microscope.TriggerMode.ONCE,
        microscope.TriggerMode.START,
    ]

    @staticmethod
    def _normalize_patterns(patterns: numpy.ndarray) -> numpy.ndarray:
        """
        Alpao SDK expects values in the [-1 1] range, so we normalize
        them from the [0 1] range we expect in our interface.
        """
        patterns = (patterns * 2) - 1
        return patterns

    def _find_error_str(self) -> str:
        """Get an error string from the Alpao SDK error stack.

        Returns:
            A string with error message.  An empty string if there was
            no error on the stack.
        """
        err_msg_buffer_len = 64
        err_msg_buffer = ctypes.create_string_buffer(err_msg_buffer_len)

        err = ctypes.pointer(asdk.UInt(0))
        status = asdk.GetLastError(err, err_msg_buffer, err_msg_buffer_len)
        if status == asdk.SUCCESS:
            msg = err_msg_buffer.value
            if len(msg) > err_msg_buffer_len:
                msg = msg + b"..."
            msg += b" (error code %i)" % (err.contents.value)
            return msg.decode()
        else:
            return ""

    def _raise_if_error(
        self, status: int, exception_cls=microscope.DeviceError
    ) -> None:
        if status != asdk.SUCCESS:
            msg = self._find_error_str()
            if msg:
                raise exception_cls(msg)

    def __init__(self, serial_number: str, **kwargs) -> None:
        super().__init__( **kwargs)
        self._dm = asdk.Init(serial_number.encode())
        if not self._dm:
            raise microscope.InitialiseError(
                "Failed to initialise connection: don't know why"
            )
        # In theory, asdkInit should return a NULL pointer in case of
        # failure and that should be enough to check.  However, at least
        # in the case of a missing configuration file it still returns a
        # DM pointer so we still need to check for errors on the stack.
        self._raise_if_error(asdk.FAILURE)

        value = asdk.Scalar_p(asdk.Scalar())
        status = asdk.Get(self._dm, b"NbOfActuator", value)
        self._raise_if_error(status)
        self._n_actuators = int(value.contents.value)
        self._trigger_type = microscope.TriggerType.SOFTWARE
        self._trigger_mode = microscope.TriggerMode.ONCE
        # setup remote focus axis
        self._axes = {'Z': remoteFocusStageAxis(limits=microscope.AxisLimits(-10.0,10.0), dm=self)}
#        self._axes = {
#            name: remoteFocusStageAxis(lim) for name, lim in limits.items()
#        }

    @property
    def n_actuators(self) -> int:
        return self._n_actuators

    @property
    def trigger_mode(self) -> microscope.TriggerMode:
        return self._trigger_mode

    @property
    def trigger_type(self) -> microscope.TriggerType:
        return self._trigger_type

    def _do_apply_pattern(self, pattern: numpy.ndarray) -> None:
        pattern = self._normalize_patterns(pattern)
        data_pointer = pattern.ctypes.data_as(asdk.Scalar_p)
        status = asdk.Send(self._dm, data_pointer)
        self._raise_if_error(status)

    def set_trigger(self, ttype, tmode):
        if tmode not in self._supported_TriggerModes:
            raise microscope.UnsupportedFeatureError(
                "unsupported trigger of mode '%s' for Alpao Mirrors"
                % tmode.name
            )
        elif (
            ttype == microscope.TriggerType.SOFTWARE
            and tmode != microscope.TriggerMode.ONCE
        ):
            raise microscope.UnsupportedFeatureError(
                "trigger mode '%s' only supports trigger type ONCE"
                % tmode.name
            )
        self._trigger_mode = tmode

        try:
            value = self._TriggerType_to_asdkTriggerIn[ttype]
        except KeyError:
            raise microscope.UnsupportedFeatureError(
                "unsupported trigger of type '%s' for Alpao Mirrors"
                % ttype.name
            )
        status = asdk.Set(self._dm, b"TriggerIn", value)
        self._raise_if_error(status)
        self._trigger_type = ttype

    def queue_patterns(self, patterns: numpy.ndarray) -> None:
        if self._trigger_type == microscope.TriggerType.SOFTWARE:
            super().queue_patterns(patterns)
            return

        self._validate_patterns(patterns)
        patterns = self._normalize_patterns(patterns)
        patterns = numpy.atleast_2d(patterns)
        n_patterns: int = patterns.shape[0]

        # The Alpao SDK seems to only support the trigger mode start.  It
        # still has option called nRepeats that we can't really figure
        # what is meant to do.  When set to 1, the mode is start.  What
        # we want it is to have trigger mode once which was not
        # supported.  We have received a modified version where if
        # nRepeats is set to same number of patterns, does trigger mode
        # once (not documented on Alpao SDK).
        if self._trigger_mode == microscope.TriggerMode.ONCE:
            n_repeats = n_patterns
        elif self._trigger_mode == microscope.TriggerMode.START:
            n_repeats = 1
        else:
            # We should not get here in the first place since
            # set_trigger filters unsupported modes.
            raise microscope.UnsupportedFeatureError(
                "trigger type '%s' and trigger mode '%s' is not supported"
                % (self._trigger_type.name, self._trigger_mode.name)
            )

        data_pointer = patterns.ctypes.data_as(asdk.Scalar_p)

        # We don't know if the previous queue of pattern ran until the
        # end, so we need to clear it before sending (see issue #50)
        status = asdk.Stop(self._dm)
        self._raise_if_error(status)

        status = asdk.SendPattern(
            self._dm, data_pointer, n_patterns, n_repeats
        )
        self._raise_if_error(status)

    def _do_shutdown(self) -> None:
        status = asdk.Release(self._dm)
        if status != asdk.SUCCESS:
            msg = self._find_error_str()
            warnings.warn(msg)

    #Functions for the remotez stage functionality.
    #Required by the stage abc
    #Properties:
    #  axes
    #  position
    #  limits
    #Methds:
    #  move_by
    #  move_to
    #Additional stuff
    #  zCalibration an array of [[pos, dm accuators pos...],[]]
    #  calcDMShape takes a position and interpolates dm shape
    #      from the calibration array
    #  setupDigitalStack to preload positons ready ofr triggers.

    @property
    def axes(self) -> typing.Mapping[str, microscope.abc.StageAxis]:
        return self._axes


    def move_by(self, delta: typing.Mapping[str, float]) -> None:
        for name, rpos in delta.items():
            self.axes[name].move_by(rpos)

    def move_to(self, position: typing.Mapping[str, float]) -> None:
        for name, pos in position.items():
            self.axes[name].move_to(pos)

    def set_zCal(self,axis,zCalibration):
        self.axes[axis].setzCalibration=zCalibration

class remoteFocusStageAxis(microscope.abc.StageAxis):
    def __init__(self, limits: microscope.AxisLimits,
                 dm: AlpaoDeformableMirror) -> None:
        super().__init__()
        self._limits = limits
        self._dm=dm
        # Start axis in the middle of its range.
        self._position = self._limits.lower + (
            (self._limits.upper - self._limits.lower) / 2.0
        )
        #calibration array is zposition followed by the zernike mode amps?
        self._zCalibration=[]


    @property
    def zCalibration(self):
        return self._zCalibration

    @zCalibration.setter
    def setzCalibration(self, calibration):
        self._zCalibration = calibration

    def save_zcalibration(self):
        numpy.save('remotez-calibration.npy',self._zCalibration)

    def load_zcalibration(self):
        self._zCalibration=numpy.load('remotez-calibration.npy')

    @property
    def position(self) -> float:
        return self._position

    @property
    def limits(self) -> microscope.AxisLimits:
        return self._limits

    def move_by(self, delta: float) -> None:
        self.move_to(self._position + delta)

#This needs to be made to calculate a Dm shape, load and trigger it
    def move_to(self, pos: float) -> None:
        if self._zCalibration[0][0]>pos:
            #position is below lower calibrated pos
            raise('position below z calibration')

        shape = self.calcDMShape(pos)
        #need to be able to call the dm shape functions.
        #apply pattern requires sw trigger
        self._dm.set_trigger(microscope.TriggerType.SOFTWARE,microscope.TriggerMode.ONCE)
        self._dm.apply_pattern(shape)
        self._position=pos

    def calcDMShape(self,pos):
       # calsteps = len(self._zCalibration)
        lastpos = self._zCalibration[0][0]
        #find cal bracketing calibration and linearly interpolate.
        for i in range (len(self._zCalibration)) :
            currentpos = self._zCalibration[i][0]
            if (currentpos > pos ):
                #this cal point and the last to bracket the pos
                interpolate = (pos-lastpos) / (currentpos-lastpos)
                dmshape = (self._zCalibration[i-1][1:]+
                         (self._zCalibration[i][1:]-self._zCalibration[i-1][1:]) *
                         interpolate)
                return(dmshape)
            lastpos=currentpos
        raise('position above z calibration')
                
                
    def setupDigitalStack(self, start: float, moveSize: float,
                          numMoves: int) -> int:
        #stacksize = moveSize * numMoves
        dm_shapes = numpy.zeros((numMoves+1,self.zCalibration.shape[1]-1))
        self.saved_pos=self._position
        #set the initial position
        self.move_to(start)
        #set trigger to hardware
        self.ttype = self._dm.trigger_type
        self.tmode = self._dm.trigger_mode
        self._dm.set_trigger(microscope.TriggerType.RISING_EDGE,
                            microscope.TriggerMode.START)
        for i in range(numMoves):
            dm_shapes[i]=(self.calcDMShape(start+moveSize*i+1))
        #final pattern is back to start to prep for next repeat
        dm_shape[numMoves+1]=self.calcDMShape(start)

        #store current trigger type to restor later
        #self.dm_trigger_mode = dm._trigger_mode
        #self.dm_trigger_type = dm._trigger_type
            #set trigger to HW
        #dm.setTrigger( microscope.TriggerType.RISING_EDGE,
        #                microscope.TriggerMode.START)
        #set the first pattern
        #queue the patterns
        self._dm.queue_patterns(dm_shapes)
        return numMoves

    #reset the trigger type in post experiment cleanup

    def cancelDigitalStack(self) -> None:
        #disable HW trigger
        self._dm.set_teigger(self.ttype,self.tmode)
        #return to original pos
        self.move_to(self.saved_pos)
