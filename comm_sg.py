#! /usr/bin/env python

# Module does not require root, merely the SG module to be loaded.
# The Lytro presents itself as a CD-ROM so being in the cdrom group is enough.
# However, this isn't perfectly stable yet; attempting a download (e.g. list pictures)
# sometimes causes the camera to crash and restart. Usually works after that, though. 

import glob, posix, fcntl, struct
from ctypes import *
import lytro

# Implement Linux SG_IO ioctl
SG_IO = 0x2285
class sg_io_hdr(Structure):
    "sg_io_hdr structure, see /usr/include/scsi/sg.h for details"
    _fields_ = [
        ('interface_id',    c_int),
        ('dxfer_direction', c_int),
        ('cmd_len',         c_ubyte),
        ('mx_sb_len',       c_ubyte),
        ('iovec_count',     c_ushort),
        ('dxfer_len',       c_uint),
        ('dxferp',          c_void_p),
        ('cmdp',            c_char_p),
        ('sbp',             POINTER(c_ubyte)),
        ('timeout',         c_uint),
        ('flags',           c_uint),
        ('pack_id',         c_int),
        ('usr_ptr',         c_void_p),
        ('status',          c_ubyte),
        ('masked_status',   c_ubyte),
        ('msg_status',      c_ubyte),
        ('sb_len_wr',       c_ubyte),
        ('host_status',     c_ushort),
        ('driver_status',   c_ushort),
        ('resid',           c_int),
        ('duration',        c_uint),
        ('info',            c_uint),
    ]
SG_DXFER_NONE = -1
SG_DXFER_TO_DEV = -2
SG_DXFER_FROM_DEV = -3

class ScsiTarget(lytro.Target):
    def __init__(self, name):
        if not name.startswith('sg:'):
            raise ValueError(f"Not a SG target: {name}")
        self.fd = posix.open(name[3:], posix.O_RDWR)
    def read(self, command, size):
        # Lytro can produce 32KiB per transfer (SG allows 64)
        sizelimit = 1<<15
        if size > sizelimit:
            size = sizelimit
        buf = create_string_buffer(size)
        hdr = sg_io_hdr(interface_id=ord('S'), timeout=1000,
                        cmdp=command, cmd_len=len(command),
                        mx_sb_len=0, #sbp=,
                        dxfer_direction=SG_DXFER_FROM_DEV,
                        dxferp=cast(pointer(buf), c_void_p), dxfer_len=size)
        result = fcntl.ioctl(self.fd, SG_IO, hdr)
        assert result==0
        # FIXME: nothing is read? our buffer seems to hold only nul
        # It works fine for the time, battery and size commands
        return buf.raw[:size-hdr.resid]
    def write(self, command, data):
        data = create_string_buffer(data)
        hdr = sg_io_hdr(interface_id=ord('S'), timeout=1000,
                        cmdp=command, cmd_len=len(command),
                        mx_sb_len=0, #sbp=cast(pointer(self.sb), POINTER(c_ubyte)),
                        dxfer_direction=SG_DXFER_TO_DEV,
                        dxferp=cast(pointer(data), c_void_p), dxfer_len=len(data))
        fcntl.ioctl(self.fd, SG_IO, hdr)

def probe():
    import pathlib
    for path in glob.glob('/sys/class/scsi_generic/sg?/device/vendor'):
        if open(path).read() == 'Lytro   \n':
            yield "sg:/dev/"+pathlib.Path(path).parts[-3]
    # CD-ROM device works for battery status, but not downloads
    #return glob.glob('/dev/disk/by-id/usb-Lytro*')

def test_getbat():
    getbat=struct.pack('<HB13x', 0xc6, 6)
    for name in probe():
        t=ScsiTarget(name)
        print("Battery level for %s: %g%%"%(name, struct.unpack('<f',t.read(getbat,4))[0]))

if __name__=='__main__':
    test_getbat()