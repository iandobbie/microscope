from microscope.cameras import atmcd
from microscope.stages import linkam

from microscope.devices import device

DEVICES = [
    device(atmcd.AndorAtmcd, 'ixon1.b24', 7777, uid='8906'),
    device(atmcd.AndorAtmcd, 'ixon2.b24', 7777, uid='8974'),
    device(linkam.LinkamCMS, 'ixon1.b24', 9000)
    ]
