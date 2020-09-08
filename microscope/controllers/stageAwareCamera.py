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
import time
import numpy as np
from PIL import Image
import scipy.ndimage

import microscope.devices as devices
import microscope.testsuite.devices

_logger = logging.getLogger(__name__)



class StageAwareCamera(microscope.testsuite.devices.TestCamera):
    def __init__(self, stage: devices.StageDevice, image, **kwargs) -> None:
        super().__init__(**kwargs)
        self._stage=stage
        self.mosaicimage = image
        #add mosaic image pattern function.
        methods=list(self._image_generator._methods)
        methods.append(self.mosaic)
        self._image_generator._methods=tuple (methods)
        #and select it.
        self.update_settings({'image pattern': len(
            self._image_generator._methods)-1})
        #load image so we can find size and channels.
        #add settings for mosaic im`ge pattern.

        self.mosaic_xpos= 0
        self.mosaic_ypos= 0
        self.mosaic_zpos=0.0
        self.mosaic_channel=0
        self._pixelsize = 1
        self.add_setting('pixelsize', 'float',
                         lambda: self._pixelsize,
                         self._set_pixelsize,
                         lambda: (0, 100))
        self.add_setting('mosaic image X pos', 'int',
                         lambda: self.mosaic_xpos,
                         self.set_mosaic_xpos,
                         lambda: (0,self.mosaicimage.size[0]))
        self.add_setting('mosaic image Y pos', 'int',
                         lambda: self.mosaic_ypos,
                         self.set_mosaic_ypos,
                         lambda: (0,self.mosaicimage.size[0]))
        self.add_setting('mosaic image Z pos', 'float',
                         lambda: self.mosaic_zpos,
                         self.set_mosaic_zpos,
                         lambda: (-50,50))
        self.add_setting('mosaic channel', 'int',
                         lambda: self.mosaic_channel,
                         self.set_mosaic_channel,
                         lambda: (0,3))


    #need a pixel size as the image must be mapped the stage coords.
    def _set_pixelsize(self, value):
        self._pixelsize = value


    def _fetch_data(self):
        if self._acquiring and self._triggered > 0:
            _logger.info('Sending image')
            time.sleep(self._exposure_time)
            self._triggered -= 1
            # Create an image
            current_pos = self._stage.position
            x=int(current_pos['x']/self._pixelsize)
            y=int(current_pos['y']/self._pixelsize)
            z=current_pos['z']
            self.update_settings({'mosaic image X pos': x})
            self.update_settings({'mosaic image Y pos': y})
            self.update_settings({'mosaic image Z pos': z})
            

            dark = 0
            light = 255
            width = self._roi.width // self._binning.h
            height = self._roi.height // self._binning.v
            image = self._image_generator.get_image(width, height, dark, light, index=self._sent)
            self._sent += 1
            return image

#mosaic getters and setters. 
    def set_mosaic_xpos(self,pos):
        self.mosaic_xpos=pos

    def get_mosaic_xpos(self):
        return self.mosaic_xpos

    def set_mosaic_ypos(self,pos):
        self.mosaic_ypos=pos

    def get_mosaic_ypos(self):
        return self.mosaic_ypos

    def set_mosaic_zpos(self,pos):
        self.mosaic_zpos=pos

    def get_mosaic_zpos(self):
        return self.mosaic_zpos

    def set_mosaic_channel(self,channel):
        self.mosaic_channel=channel

    def get_mosaic_channel(self):
        return self.mosaic_channel

    #deal with actual mosaic image return.
    def mosaic(self, w, h, dark, light):
        """Returns subsections of a mosaic image based on input coords"""
        if not self.mosaicimage:
            self.loadimage("microscope/testsuite/mosaicimage.tif")
#            self.redmosaic,self.greenmosaic,self.bluemosaic=self.mosaicimage.split()
        x=self.mosaic_xpos+(self.mosaicimage.size[0]/2)
        y=self.mosaic_ypos+(self.mosaicimage.size[1]/2)
        blur=abs((self.mosaic_zpos)/10)
        #return a section of the image
        #take moasic channel mod number of channels. 
        imgSection=self.mosaicimage.getchannel(
            self.mosaic_channel%len(self.mosaicimage.getbands())).crop((x-w/2,y-h/2,x+w/2,y+h/2))
        #gaussian filter on abs Z position to simulate focus
        return (scipy.ndimage.gaussian_filter(np.asarray(
            imgSection.getdata()).reshape(w,h),blur))

    def loadimage(self, imagefile):
        self.moasaicimage=Image.open(imagefile)

# The controller is not necessary at all, a user could perfectly
# create its own camera and stage, it's only to make device server
# easier to use.
class CameraStageController(devices.ControllerDevice):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        #load image and set moasic size for stage.
        self.mosaicimage=Image.open("microscope/testsuite/mosaicimage.tif")
        mosaicSize=self.mosaicimage.size[:2]
        #initialise stage
        stage = microscope.testsuite.devices.TestStage({
            'x' : devices.AxisLimits(-mosaicSize[0]/2, mosaicSize[0]/2),
            'y' : devices.AxisLimits(-mosaicSize[1]/2, mosaicSize[1]/2),
            'z' : devices.AxisLimits(-50, 50)
        })
        self._stage=stage

        #init camera and configure.
        camera = StageAwareCamera(stage, self.mosaicimage)
        camera.update_settings({'pixelsize': 1.0})
     
        # filterwheel = microscope.testsuite.devices.TestFilterWheel()
        # self._filterwheel = filterwheel
        #list devices
        self._devices = {'stage' : stage, 'camera' : camera}
#                         'filterwheel': filterwheel}

        
    @property
    def devices(self):
        return self._devices


