#! /usr/bin/env python

# Talks to Lytro via USB mass storage bulk protocol
# Using PyUSB

import struct
import usb.core
import lytro

# The Lytro speaks Mass Storage, SFF-8070i subclass.
# That is obsolete, yay me.
# It has two configurations for unknown reasons.
# It presents a CD-ROM with a link to the (dead) site.
# The protocol is listed as 80, which is 50h=mass storage class bulk-only (BBB).

class UsbTarget(lytro.Target):
    def __init__(self, dev):
        self.handle = dev
        # TODO: parse configuration for endpoints?
        # Verify that it is in fact the correct protocol?
        try:
            self.handle.detach_kernel_driver(0)
        except usb.USBError:
            pass
#        self.handle.claim_interface(0)
        self.epout = 2
        self.epin = 0x82
        #for ep in self.epin, self.epout:
        #    self.handle.resetEndpoint(ep)
        self.tag=0
        # Try to read out leftovers? Reset device?
        self.flushIn()
    def flushIn(self):
        data = True
        while data:
            try:
                data = self.handle.read(self.epin, 128, 100)
            except usb.core.USBError:
                break
            print(f"Flushed: {data!r}")
    def newTag(self):
        self.tag+=1
        return self.tag
    def read(self, command, size):
        self.handle.write(self.epout,
                              struct.pack('<4sIIBBB16s', b'USBC', self.newTag(),
                                          size, 0x80, 0, len(command), command),
                              100)
        data = b''
        while len(data)<size:
            data += self.handle.read(self.epin, size-len(data), 1000)
        # FIXME: Second call here gets a Pipe error during download?
        #print "Got data: ", repr(data)
        csw=self.handle.read(self.epin, 13, 100)   # TODO: Error handling. Not that Lytro did any...
        return bytearray(data)
    def write(self, command, data):
        self.handle.write(self.epout,
                              struct.pack('<4sIIBBB16s', b'USBC', self.newTag(),
                                          len(data), 0, 0, len(command), command),
                              100)
        if data:
            self.handle.write(self.epout, data, 100)
        # Read status packet (TODO: handle it!)
        csw=self.handle.read(self.epin, 13, 100)
        

def probe():
    # This produces the device connection.
    # I don't know a way to convert to/from a path in PyUSB.
    # The fields listed in the repr are idVendor, idProduct, bus, address
    # Quite possibly that can be parsed.
    return usb.core.find(find_all=True, idVendor=0x24cf, idProduct=0x00a1)

if __name__=='__main__':
    getbat=struct.pack('<HB13x', 0xc6, 6)
    for name in probe():
        print(repr(name))
        #print(dir(name.dev))
        t=UsbTarget(name)
        level = struct.unpack('<f',t.read(getbat,4))[0]
        print(f"Battery level for {repr(name)}: {level}%")

