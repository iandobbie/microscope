#!/usr/bin/env python
# -*- coding: utf-8 -*-

## Copyright (C) 2019 David Miguel Susano Pinto <david.pinto@bioch.ox.ac.uk>
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

"""Zaber devices.

This module only controls Zaber devices via the ASCII protocol meaning
it can be used with A-Series and X-Series devices that have firmware
6.06 or higher.

"""

import serial
import threading
import typing

import microscope.devices


class _ZaberReply:
    """Wraps a Zaber reply to easily index its multiple fields."""
    def __init__(self, data: bytes) -> None:
        self._data = data
        # 64 is b'@' and 32 is b' ' (space)
        if data[0] != 64 or any([data[i] != 32 for i in (3, 5, 8, 13, 16)]):
            raise ValueError('Not a valid reply from a Zaber device')

    @property
    def address(self) -> bytes:
        """The start of reply with device address and space."""
        return self._data[1:3]

    @property
    def flag(self) -> bytes:
        """The reply flag indicates if the message was accepted or rejected.

        Can be b'OK' (accepted) or b'RJ' (rejected0.  If rejected, the
        response property will be one word with the reason why.
        """
        return self._data[6:8]

    @property
    def warning(self) -> bytes:
        """The highest priority warning currently active.

        This will be b'--' under normal conditions.  Anything else is
        a warning.
        """
        return self._data[14:16]

    @property
    def response(self) -> bytes:
        # Assumes no checksum
        return self._data[17:-2]


class _ZaberConnection:
    """Wraps a serial connection with a reentrant lock.

    The commands to the device are on the `_ZaberDeviceConnection`
    class which wraps the logic of routing the commands to the correct
    device in the chain.
    """
    def __init__(self, port: str, baudrate: int, timeout: float) -> None:
        self._serial = serial.Serial(port=port, baudrate=baudrate,
                                     timeout=timeout, bytesize=serial.EIGHTBITS,
                                     stopbits=serial.STOPBITS_ONE,
                                     parity=serial.PARITY_NONE,
                                     xonxoff=False, rtscts=False,
                                     dsrdtr=False)
        self._lock = threading.RLock()
        with self._lock:
            # The command / does nothing other than getting a response
            # from all devices in the chain.  This seems to be the
            # least innocent command we can use.
            self._serial.write(b'/\n')
            lines = self._serial.readlines()
        if not all([l.startswith(b'@') for l in lines]):
            raise RuntimeError('\'%s\' does not respond like a Zaber device'
                               % port)

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def write(self, data: bytes) -> int:
        with self.lock:
            return self._serial.write(data)

    def readline(self, size: int = -1) -> bytes:
        with self.lock:
            return self._serial.readline(size)


class _ZaberDeviceConnection:
    """A Zaber connection to control a single device.
    """
    def __init__(self, conn: _ZaberConnection, device_address: int) -> None:
        self._conn = conn
        self._address_bytes = b'%02d' % device_address

    def _validate_reply(self, reply: _ZaberReply) -> None:
        if reply.address != self._address_bytes:
            raise RuntimeError('received reply from a device with different'
                               ' address (%s instead of %s)'
                               % (reply.address.decode(),
                                  self._address_bytes.decode()))
        elif reply.flag != b'OK':
            raise RuntimeError('command rejected because \'%s\''
                               % reply.response.decode())

    def command(self, command: bytes, axis: int = 0) -> _ZaberReply:
        """Command

        Args:
            command (bytes): a bytes array with the command and its
                parameters.
            axis (int): the axis number to send the command.  If zero,
                the command is executed by all axis in the device.
        """
        # We do not need to check whether axis number is valid because
        # the device will reject the command with BADAXIS if so.
        with self._conn.lock:
            self._conn.write(b'/%s %1d %s\n'
                             % (self._address_bytes, axis, command))
            data = self._conn.readline()
        reply = _ZaberReply(data)
        self._validate_reply(reply)
        return reply

    def get_number_axes(self) -> int:
        return int(self.command(b'get system.axiscount').response)

    def been_homed(self, axis: int = 0) -> bool:
        """True if all axes, or selected axis, has been homed."""
        reply = self.command(b'get limit.home.triggered', axis)
        return all([int(x) for x in reply.response.split()])

    def home(self, axis: int = 0) -> None:
        """Move the axis to the home position."""
        self.command(b'home', axis)

    def get_rotation_length(self, axis: int) -> int:
        """Number of microsteps needed to complete one full rotation.

        This is only valid on controllers and rotary devices including
        filter wheels and filter cube turrets.
        """
        return int(self.command(b'get limit.cycle.dist', axis).response)

    def get_index_distance(self, axis: int) -> int:
        return int(self.command(b'get motion.index.dist', axis).response)

    def get_current_index(self, axis: int) -> int:
        return int(self.command(b'get motion.index.num', axis).response)

    def move_to_index(self, axis: int, index: int) -> None:
        self.command(b'move index %d' % index, axis)

    def move_to_absolute_position(self, axis: int, position: int) -> None:
        self.command(b'move abs %d' % position, axis)

    def move_by_relative_position(self, axis: int, position: int) -> None:
        self.command(b'move rel %d' % position, axis)

    def get_absolute_position(self, axis: int) -> int:
        """Current absolute position of an axis, in microsteps."""
        return int(self.command(b'get pos', axis).response)

    def get_limit_max(self, axis: int) -> int:
        """The maximum position the device can move to, in microsteps."""
        return int(self.command(b'get limit.max', axis).response)

    def get_limit_min(self, axis: int) -> int:
        """The minimum position the device can move to, in microsteps."""
        return int(self.command(b'get limit.min', axis).response)


class _ZaberStageAxis(microscope.devices.StageAxis):
    def __init__(self, conn: _ZaberDeviceConnection, axis: int) -> None:
        super().__init__()
        self._conn = conn
        self._axis = axis

    def move_by(self, delta: float) -> None:
        self._conn.move_by_relative_position(self._axis, int(delta))

    def move_to(self, pos: float) -> None:
        self._conn.move_to_absolute_position(self._axis, int(pos))

    @property
    def position(self) -> float:
        return float(self._conn.get_absolute_position(self._axis))

    @property
    def limits(self) -> microscope.devices.AxisLimits:
        min_limit = self._conn.get_limit_min(self._axis)
        max_limit = self._conn.get_limit_max(self._axis)
        return microscope.devices.AxisLimits(lower=min_limit,
                                             upper=max_limit)


class _ZaberStage(microscope.devices.StageDevice):
    def __init__(self, conn: _ZaberConnection, device_address: int,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._conn = _ZaberDeviceConnection(conn, device_address)
        self._axes = {str(i): _ZaberStageAxis(self._conn, i) for i in range(1,self._conn.get_number_axes()+1)}

    def initialize(self) -> None:
        super().initialize()

    def _on_shutdown(self) -> None:
        super()._on_shutdown()

    def _on_enable(self) -> bool:
        # Before a device can moved, it first needs to establish a
        # reference to the home position.  We won't be able to move
        # unless we home it first.
        if not self._conn.been_homed():
            self._conn.home()
        return True

    @property
    def axes(self) -> typing.Mapping[str, microscope.devices.StageAxis]:
        return self._axes

    @property
    def position(self) -> typing.Mapping[str, float]:
        return {name: axis.position for name, axis in self._axes.items()}

    @property
    def limits(self) -> typing.Mapping[str, microscope.devices.AxisLimits]:
        return {name: axis.limits for name, axis in self._axes.items()}

    def move_by(self, delta: typing.Mapping[str, float]) -> None:
        """Move specified axes by the specified distance. """
        for axis_name, axis_delta in delta.items():
            self._axes[axis_name].move_by(axis_delta)

    def move_to(self, position: typing.Mapping[str, float]) -> None:
        """Move specified axes by the specified distance. """
        for axis_name, axis_position in position.items():
            self._axes[axis_name].move_to(axis_position)


class _ZaberFilterWheel(microscope.devices.FilterWheelBase):
    """Zaber filter wheels and filter cube turrets.
    """
    def __init__(self, conn: _ZaberConnection, device_address: int,
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._conn = _ZaberDeviceConnection(conn, device_address)

        if self._conn.get_number_axes() != 1:
            raise RuntimeError('Device with address %d is not a filter wheel'
                               % (device_address))

        rotation_length = self._conn.get_rotation_length(1)
        if rotation_length <= 0:
            raise RuntimeError('Device with address %d is not a filter wheel'
                               % (device_address))
        self._positions = int(rotation_length
                              / self._conn.get_index_distance(1))

        # Before a device can moved, it first needs to establish a
        # reference to the home position.  We won't be able to move
        # unless we home it first.  On a stage this happens during
        # enable because the stage movemenet can be dangerous but on a
        # filter wheel this is fine.
        if not self._conn.been_homed():
            self._conn.home()

    def initialize(self) -> None:
        super().initialize()

    def _on_shutdown(self) -> None:
        super()._on_shutdown()

    def get_position(self) -> int:
        # Zaber positions start at one.
        # FIXME: Microscope is not clear on what position number it
        # counts from (issue #119).  This might require fixing later.
        return self._conn.get_current_index(axis=1)

    def set_position(self, position: int) -> None:
        # Zaber positions start at one.
        # FIXME: Microscope is not clear on what position number it
        # counts from (issue #119).  This might require fixing later.
        if position < 1 or position > self._positions:
            raise ValueError('position number must be between 1-%d inclusive'
                             % self._positions)
        self._conn.move_to_index(axis=1, index=position)


class ZaberDaisyChain(microscope.devices.ControllerDevice):
    """A daisy chain of Zaber devices.

    Args:
        port (str): the port name to connect to.  For example,
            `/dev/ttyS1`, `COM1`, or `/dev/cuad1`.
        address2type (dict[type, str]): maps `microscope.Device` ABCs,
            to a specific device address.  For example,
            `{microscope.FilterWheelBase : 3}` to control a filter
            wheel device with the device address 3.

    Zaber devices can be daisy-chained.  In such setup, only the first
    device is connected to the computer and there is one communication
    port which is shared between all devices.  Modelling such setup as
    a controller device type helps in ensuring that messages go to the
    correct device.  Even a single Zaber device is a daisy-chain of
    one single device.

    Each device on a chain is identified by a device address which is
    an integer between 1 and 99.  By default, the addresses start at 1
    and are sorted by distance to the computer.  However, this can be
    changed.

    Because there is no method to correctly guess a device type, a map
    of device addresses to device types is required.

    .. note::

       While the device address used to construct the controller are
       integers, the devices property will use a string on the map
       like all other :class:`microscope.ControllerDevice` types.

    .. note::

       Zaber devices need to be homed before they can be moved.  Any
       device that has not been homed will do so when the object is
       constructed.

    .. todo::

       Create non controller classes for the simpler case where there
       is only one zaber device, and modelling it as controller device
       is non obvious.

    """
    def __init__(self, port: str,
                 address2type: typing.Mapping[int, typing.Type],
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self._conn = _ZaberConnection(port, baudrate=115200, timeout=0.5)
        self._devices: typing.Mapping[str, microscope.devices.Device] = {}

        # Map the possible microscope device types to concrete
        # implementations in this module to keep the concrete
        # implementations private for now.
        _abc2cls = {
            microscope.devices.FilterWheelBase : _ZaberFilterWheel,
            microscope.devices.StageDevice : _ZaberStage,
        }

        for address, base_type in address2type.items():
            if address < 1 or address > 99:
                raise ValueError('address must be an integer between 1-99')
            if not base_type in _abc2cls:
                raise ValueError('device of type \'%s\' are not supported'
                                 % base_type)
            self._devices[str(address)] = _abc2cls[base_type](self._conn,
                                                              address)

    @property
    def devices(self) -> typing.Mapping[str, microscope.devices.Device]:
        return self._devices
