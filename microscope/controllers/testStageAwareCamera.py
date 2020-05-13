#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (C) 2020 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
# Copyright (C) 2020 Ian Dobbue <ian.dobiie@bioch.ox.ac.uk>
#
# Microscope is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Microscope is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Microscope.  If not, see <http://www.gnu.org/licenses/>.

"""Test controller device that merges a test stage with a test camera 
in mosaic mode.

This mosaic type functionality to be tested as the camera returns 
different data dependant upon the stage position. 
"""

import logging
import typing

import microscope.devices as devices
import microscope.testsuite.devices

_logger = logging.getLogger(__name__)



class StageAwareCamera(devices.CameraDevice):
    def __init__(self, stage: devices.StageDevice, image: str, **kwargs) -> None:
    
        self._stage=stage
        self.realCam=microscope.testsuite.devices.TestCamera()
        self.realCam.update_settings({'image pattern': 6})



    def _fetch_data(self):
        current_pos = self._stage.position
        x=current_pos['x']
        y=current_pos['y']
        self.realCam.update_settings({'mosaic image X pos': x,
                                'mosaic image Y pos': y})
        # Compute the indices for the image ndarray from the position
        return self.realCam._fetch_data()
    
    def _set_error_percent(self, value):
        self.realCam._set_error_percent(value)


    def _set_gain(self, value):
        self.reCsm._set_gain(value)

    def _purge_buffers(self):
        self.reCsm._purge_buffers()

    def _create_buffers(self):
        self.reCsm._create_buffers()

    def abort(self):
        self.realCam.abort()

    def initialize(self):
        self.realCam.initialize()

    def make_safe(self):
        self.realCam.make_safe()

    def _on_disable(self):
        self.abort()

    def _on_enable(self):
        return(self.realCam._on_enable())

    def set_exposure_time(self, value):
        self.realCam.set_exposure_time(value)

    def get_exposure_time(self):
        return self.realCam._exposure_time

    def get_cycle_time(self):
        return self.realCam._exposure_time

    def _get_sensor_shape(self):
        return (512,512)

    def get_trigger_type(self):
        return devices.TRIGGER_SOFT

    def soft_trigger(self):
        self.realCam.soft_trigger()

    def _get_binning(self):
        return self.realCam._binning

    def _set_binning(self, binning):
        self.realCam._set_binning(binning)

    def _get_roi(self):
        return self.realCam._roi

    def _set_roi(self, roi):
        self.realCam._set_roi(roi)

    def _on_shutdown(self):
        pass

    @property
    def _acquiring(self):
        return (self.realCam._aquiring)
    @property
    def _settings(self):
        return(self.realCam._settings)
    
# The controller is not necessary at all, a user could perfectly
# create its own camera and stage, it's only to make device server
# easier to use.
class CameraStageController(devices.ControllerDevice):
    def __init__(self):
        mosaicSize=(9562,9458)
        stage = microscope.testsuite.devices.TestStage({
            'x' : devices.AxisLimits(-mosaicSize[0]/2, mosaicSize[0]/2),
            'y' : devices.AxisLimits(-mosaicSize[1]/2, mosaicSize[1]/2),
        })
        self._stage=stage
        camera = StageAwareCamera(stage, "microscope/testsuite/mosaicimage.tif" )
        self._devices = {'stage' : stage, 'camera' : camera}

    @property
    def devices(self):
        return self._devices


