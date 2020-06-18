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
import random
import time

import microscope.devices as devices
import microscope.testsuite.devices

_logger = logging.getLogger(__name__)



class StageAwareCamera(microscope.testsuite.devices.TestCamera):
    def __init__(self, stage: devices.StageDevice, image: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stage=stage
        self.update_settings({'image pattern': 6})
        print (image)


    def _fetch_data(self):
        if self._acquiring and self._triggered > 0:
            if random.randint(0, 100) < self._error_percent:
                _logger.info('Raising exception')
                raise Exception('Exception raised in TestCamera._fetch_data')
            _logger.info('Sending image')
            time.sleep(self._exposure_time)
            self._triggered -= 1
            # Create an image
            current_pos = self._stage.position
            x=current_pos['x']
            y=current_pos['y']
            self.update_settings({'mosaic image X pos': x,
                                  'mosaic image Y pos': y})
            dark = 0
            light = 255
            width = self._roi.width // self._binning.h
            height = self._roi.height // self._binning.v
            image = self._image_generator.get_image(width, height, dark, light, index=self._sent)
            self._sent += 1
            return image
    
# The controller is not necessary at all, a user could perfectly
# create its own camera and stage, it's only to make device server
# easier to use.
class CameraStageController(devices.ControllerDevice):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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


