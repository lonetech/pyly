#! /usr/bin/env python

# Talks to Lytro via USB mass storage bulk protocol

import usb, struct, lytro

# The Lytro speaks Mass Storage, SFF-8070i subclass.
# That is obsolete, yay me.
# It has two configurations for unknown reasons.
# It presents a CD-ROM with a link to the (dead) site.
# The protocol is listed as 80, which is 50h=mass storage class bulk-only (BBB).

class UsbTarget(lytro.Target):
    def __init__(self, name):
        self.handle = name.open()
        # TODO: parse configuration for endpoints?
        # Verify that it is in fact the correct protocol?
        try:
            self.handle.detachKernelDriver(0)
        except usb.USBError:
            pass
        self.handle.claimInterface(0)
        self.epout = 2
        self.epin = 0x82
        for ep in self.epin, self.epout:
            self.handle.resetEndpoint(ep)
        self.tag=0
        # Try to read out leftovers? Reset device?
        self.flushIn()
    def flushIn(self):
        data = True
        while data:
            try:
                data = self.handle.bulkRead(self.epin, 128, 100)
            except usb.core.USBError:
                break
            print(f"Flushed: {data!r}")
    def newTag(self):
        self.tag+=1
        return self.tag
    def read(self, command, size):
        self.handle.bulkWrite(self.epout,
                              struct.pack('<4sIIBBB16s', b'USBC', self.newTag(),
                                          size, 0x80, 0, len(command), command),
                              100)
        data = b''
        while len(data)<size:
            data += self.handle.bulkRead(self.epin, size-len(data), 1000)
        # FIXME: Second call here gets a Pipe error during download?
        #print "Got data: ", repr(data)
        csw=self.handle.bulkRead(self.epin, 13, 100)
        return bytearray(data)
    def write(self, command, data):
        self.handle.bulkWrite(self.epout,
                              struct.pack('<4sIIBBB16s', b'USBC', self.newTag(),
                                          len(data), 0, 0, len(command), command),
                              100)
        if data:
            self.handle.bulkWrite(self.epout, data, 100)
        # Read status packet (TODO: handle it!)
        csw=self.handle.bulkRead(self.epin, 13, 100)
        

def probe():
    return [device for bus in usb.busses()
            for device in bus.devices if device.idVendor==0x24cf]

if __name__=='__main__':
    getbat=struct.pack('<HB13x', 0xc6, 6)
    for name in probe():
        t=UsbTarget(name)
        print("Battery level for %s: %g%%"%(name, struct.unpack('<f',t.read(getbat,4))[0]))
    
