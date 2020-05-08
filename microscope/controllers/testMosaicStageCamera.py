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


class TestMosaicStageCamera(microscope.devices.ControllerDevice):
    """Test controller device 

    Args:

    .. code-block:: python

       # Connect to test stage and camera 
       controller = TestMosaicStageCamera()
    """
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        #config camera for mosic mode. and find image size
        camera = microscope.testsuite.devices.TestCamera()
        camera.update_settings({'image pattern': 6})
        mosaicSize=(9562,9458)
        
        #config stage
        stage = StageIndirection(camera=camera)
        self._devices = {
            'camera' : camera,
            'stage' : stage,
        }

    @property
    def devices(self):
        return self._devices
    
class StageIndirection(devices.StageDevice,camera):
    '''Intercept stage calls, and adjust camera mosaic xpos before passing
        calls on to stage itself'''
    def __init__(self,**kwargs) -> None:
        super().__init__(**kwargs)
        self.camera=camera
        self.realStage=microscope.testsuite.devices.TestStage({
            'x' : devices.AxisLimits(-mosaicSize[0]/2, mosaicSize[0]/2),
            'y' : devices.AxisLimits(-mosaicSize[1]/2, mosaicSize[1]/2),
        })
            
        self._axes = self.realStage._axes
            
    def initialize(self):
        pass
            
    def _on_shutdown(self):
        pass
            
    def axes(self):
        return self._axes
            
    def move_by(self, delta):
        curx=self.camera.get_setting('mosaic image X pos')
        cury=self.camera.get_setting('mosaic image Y pos')
        
        for name, rpos in delta.items():
            if name == 'x' :
                newpos=curx+rpos
                self.camera.update_setting({'mosaic image X pos': newpos})
            if name == 'y' :
                newpos=cury+rpos
                self.camera.update_setting({'mosaic image Y pos': newpos})
        self.realStage.move_by(delta)
                    
                
    def move_to(self, position):
        for name, pos in position.items():
            if name == 'x' :
                newpos=pos
                self.camera.update_setting({'mosaic image X pos': newpos})
            if name == 'y' :
                newpos=pos
                self.camera.update_setting({'mosaic image Y pos': newpos})
        self.realStage.move_to(position)

