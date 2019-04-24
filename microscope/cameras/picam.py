#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2016-2017 Mick Phillips <mick.phillips@gmail.com>
## Copyright (C) 2019 Ian Dobbie <ian.dobbie@bioch.ox.ac.uk>
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

import time

import Pyro4
import numpy as np

from microscope import devices
from microscope.devices import keep_acquiring

#import raspberry pi specific modules
import picamera
from io import BytesIO




# Trigger mode to type.
TRIGGER_MODES = {
    'internal': None,
    'external': devices.TRIGGER_BEFORE,
    'external start': None,
    'external exposure': devices.TRIGGER_DURATION,
    'software': devices.TRIGGER_SOFT,
}


@Pyro4.expose
@Pyro4.behavior('single')
class PiCamera(devices.CameraDevice):
    def __init__(self, *args, **kwargs):
        super(PiCamera, self).__init__(**kwargs)
#example parameter to allow setting.
#        self.add_setting('_error_percent', 'int',
#                         lambda: self._error_percent,
#                         self._set_error_percent,
#                         lambda: (0, 100))
        self._acquiring = False
        self._exposure_time = 0.1
        self._triggered = False
        self.camera = None


    def _purge_buffers(self):
        """Purge buffers on both camera and PC."""
        self._logger.info("Purging buffers.")

    def _create_buffers(self):
        """Create buffers and store values needed to remove padding later."""
        self._purge_buffers()
        self._logger.info("Creating buffers.")
        #time.sleep(0.5)

    def _fetch_data(self):
        if self._acquiring and self._triggered:
            with picamera.array.PiYUVArray(camera) as output:
                self.camera.capture(output, format='yuv', use_video_port = False)
                #just return intensity values
                self._logger.info('Sending image')
                self._triggered = False
                return(output[:,:,0])

    def initialize(self):
        """Initialise the Pi Camera camera.
        Open the connection, connect properties and populate settings dict.
        """
        if not self.camera:
            try:
                #initialise camera in still image mode.
                self.camera  = picamera.PiCamera(sensor_mode=2)
            except:
                raise Exception("Problem opening camera.")
        self._logger.info('Initializing camera.')
        #create img buffer to hold images.
        #disable camera LED by default
        self.setLED(False)
 
    #set camera LED status, off is best for microscopy.
    def setLED(self, state=False):
        self.camera.led(state)


    def set_exposure_time(self, value):
        #exposure times are set in us.
        self.camera.shutter_sppeed=(int(value*1.0E6))


    def get_exposure_time(self):
        #exposure times are in us, so multiple by 1E-6 to get seconds.
        return (self.camera.exposure_speed*1.0E-6) 


    def _get_sensor_shape(self):
        return (self.camera.resolution)


#ongoing implemetation notes

#should be able to use rotation and hflip to set specific output image
# rotations

#roi's can be set with the zoom function, default is (0,0,1,1) meaning all the data.




##old cockpit based picam driver
#    def __init__(self):
#         self.camera = None
#         self.guid = None
#         self.cameraInfo = None
#         self.connected = False
#         self.client = None
#         self.lastImage = None
#         self.imgRaw = None
#         self.width = 512
#         self.height = 512
        
        
#     def __del__(self):
#         c = self.camera
#         if not c:
#             return
#         try:
#             #try to close the current camera connection to release
#             #resources.
#             self.camera.close()
#         except:
#             pass


#     def connect(self, index=0):
#         if not self.camera:
#             self.camera  = picamera.PiCamera()
#         if not self.camera:
#             raise Exception('No camera found.')

#         #picam setup
#         #set max resolutioon for still capture
#         self.camera.resolution = (self.width, self.height)
#         # use string CAMERA_RESOLUTION to get max resolution
#         self.connected = True
#         #disable camera LED by default
#         self.setLED(False)
                

#     def enableCamera(self):
#         if not self.connected: self.connect()
#         return True


#     def disableCamera(self):
#         if not self.connected or not self.camera:
#             return
#         self.camera.close()
#         return False


#     def grabImageToDisk(self, outFileName='picam-Test.png'):
#         stream = BytesIO()
#         self.camera.capture(stream,format='yuv')
#         stream.seek(0)
#         open(outFileName, 'wb').write(stream.getvalue())
       

    
#     def grabImageToBuffer(self):
#         #setup stream, numpy from file only acepts a real file so....
#         stream = open('image.data', 'w+b')
#         #grab yuv image to stream
#         self.camera.capture(stream,format='yuv')
#         #seek back to start of stream
#         stream.seek(0)
#         #pull out the Y channel (luminessence) as 8 bit grey
#         imgConv = np.fromfile(stream, dtype=np.uint8,
#                               count=self.width*self.height).reshape((self.height,
#                                                                      self.width))
#           self.lastImage = imgConv

#     def getImageSize(self):
#         width, height = self.width, self.height
#         return (int(width), int(height))


#     def getImageSizes(self):
#         return [self.width,self.height]


#     def getTimeBetweenExposures(self, isExact=False):
#         if isExact:
#             return decimal.Decimal(0.1)
#         else:
#             return 0.1


#     def getExposureTime(self, isExact=False):
#         if isExact:
#             return decimal.Decimal(0.1)
#         else:
#             return 0.1


#     def setExposureTime(self, time):
#         pass


#     def setImageSize(self, size):
#         pass


#     #set camera LED status, off is best for microscopy.
#     def setLED(self, state=False):
#         self.camera.led(state)
    
#     def softTrigger(self):
#         if self.client is not None:
#             self.grabImageToBuffer()
#             self.client.receiveData('new image',
#                                      self.lastImage,
#                                      time.time())


#     def receiveClient(self, uri):
#         """Handle connection request from cockpit client."""
#         if uri is None:
#             self.client = None
#         else:
#             self.client = Pyro4.Proxy(uri)


# def main():
#     print sys.argv
#     host = '10.0.0.2' or sys.argv[1]
#     port = 8000 or int(sys.argv[2])
#     daemon = Pyro4.Daemon(port=port, host=host)

#     # Start the daemon in a new thread so we can exit on ctrl-c
#     daemonThread = threading.Thread(
#         target=Pyro4.Daemon.serveSimple,
#         args = ({Camera(): 'pyroCam'},),
#         kwargs = {'daemon': daemon, 'ns': False}
#         )
#     daemonThread.start()

#     while True:
#         try:
#             time.sleep(1)
#         except KeyboardInterrupt:
#             break

#     daemon.shutdown()
#     daemonThread.join()


# if __name__ == '__main__':
#     main()
