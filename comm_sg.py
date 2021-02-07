#! /usr/bin/env python

# Note: CAP_SYS_RAWIO is required to run the vendor specific SCSI commands.
# This basically means this module requires root.
# TODO: Find a neat way to request root or the capability. 

import glob, posix, fcntl, struct
from ctypes import *
import lytro

# Implement Linux SG_IO ioctl
SG_IO = 0x2285
class sg_io_hdr(Structure):
    "sg_io_hdr structure, see /usr/include/scsi/sg.h for details"
    _fields_ = [
        ('interface_id',	c_int),
        ('dxfer_direction',	c_int),
        ('cmd_len',		c_ubyte),
        ('mx_sb_len',		c_ubyte),
        ('iovec_count',		c_ushort),
        ('dxfer_len',		c_uint),
        ('dxferp',		c_void_p),
        ('cmdp',		c_char_p),
        ('sbp',			POINTER(c_ubyte)),
        ('timeout',		c_uint),
        ('flags',		c_uint),
        ('pack_id',		c_int),
        ('usr_ptr',		c_void_p),
        ('status',		c_ubyte),
        ('masked_status',	c_ubyte),
        ('msg_status',		c_ubyte),
        ('sb_len_wr',		c_ubyte),
        ('host_status',		c_ushort),
        ('driver_status',	c_ushort),
        ('resid',		c_int),
        ('duration',		c_uint),
        ('info',		c_uint),
    ]

class ScsiTarget(lytro.Target):
    sb_len = 0
    def __init__(self, name):
        self.fd = posix.open(name, posix.O_RDWR | posix.O_NONBLOCK)
        self.sb = create_string_buffer(self.sb_len)
    def read(self, command, size):
        if size>2048:
            size=65536
        buf = create_string_buffer(size)
        #print "Buffer size: ", len(buf)
        hdr = sg_io_hdr(interface_id=ord('S'), timeout=1000,
                        cmdp=command, cmd_len=len(command),
                        mx_sb_len=self.sb_len, sbp=cast(pointer(self.sb), POINTER(c_ubyte)),
                        dxfer_direction=-3, dxferp=cast(pointer(buf), c_void_p), dxfer_len=size)
        result = fcntl.ioctl(self.fd, SG_IO, hdr)
        assert result==0
        # FIXME: nothing is read? our buffer seems to hold only nul
        # It works fine for the time, battery and size commands
        return buf.raw
    def write(self, command, data):
        data = create_string_buffer(data)
        hdr = sg_io_hdr(interface_id=ord('S'), timeout=1000,
                        cmdp=command, cmd_len=len(command),
                        mx_sb_len=self.sb_len, sbp=cast(pointer(self.sb), POINTER(c_ubyte)),
                        dxfer_direction=-2, dxferp=cast(pointer(data), c_void_p), dxfer_len=len(data))
        fcntl.ioctl(self.fd, SG_IO, hdr)
    

def probe():
    return glob.glob('/dev/disk/by-id/usb-Lytro*')

if __name__=='__main__':
    getbat=struct.pack('<HB13x', 0xc6, 6)
    for name in probe():
        t=ScsiTarget(name)
        print("Battery level for %s: %g%%"%(name, struct.unpack('<f',t.read(getbat,4))[0]))
