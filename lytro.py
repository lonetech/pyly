import datetime
import struct

# Protocol references:
#  http://optics.miloush.net/lytro/TheProtocols.Commands.aspx
#  https://ljirkovsky.wordpress.com/2015/03/16/lytro-protocol/

from typing import Dict, Optional, Callable, Any

# Abstract base class for communication modes
class Target:
    pass

# Download IDs
loadtypes = {
    'hardware_info': 0,
    'file': 1,
    'picture_list': 2,
    'picture': 5,
    'calibration': 6,
    'rawcompressedpicture': 7,
}
picturesubtypes = 'jpg,raw,txt,128,stk'.split(',')

class LytroPacket(object):
    headerstruct="<IIIH" # Magic, content length, flags, command
    paramsstruct="14x"
    params=()
    magic=0xfaaa55af
    length=0
    flags=0
    payload=b''
    def send(self, s):
        packet=struct.pack('Bx'+self.paramsstruct, self.command, *self.params)
        if not self.flags&1:
            data=self.payload.ljust(self.length,b'\0')
            #print(f"Write command: {packet!r} {data!r}")
            s.write(packet, data)
        else:
            #print("Read command: {packet!r} {self.length}")
            response=s.read(packet, self.length)
            if self.length and response:
                # Handle incoming data
                return self.read(self.command, packet[2:], response)
        return None
    @classmethod
    def read(self, command, params, payload):
        try:
            return LytroResponses[command](params,payload)
        except KeyError:
            raise IOError(f"Unknown packet: {params!r} {payload!r}")

LytroQueries = {}
class LytroQuery(LytroPacket):
    flags=1
    command=0xc6
    paramsstruct="B13x"
    def unpack(self):
        return struct.unpack(self.payloadstruct, self.payload)
    @classmethod
    def response(self, params, payload):
        (query,)=struct.unpack(self.paramsstruct, params)
        return LytroQueries[query](payload)

class LytroQueryBattery(LytroQuery):
    payloadstruct = '<f'
    length = 4
    query = 6
    params = (query,)
    def __init__(self, payload=None):
        self.payload = payload
    def percent(self):
        return self.unpack()[0]
LytroQueries[LytroQueryBattery.query] = LytroQueryBattery

class LytroQueryTime(LytroQuery):
    payloadstruct = "<7H"
    length = struct.calcsize(payloadstruct)
    query = 3
    params = (query,)
    def __init__(self, payload=None):
        self.payload = payload
    def datetime(self):
        dt = self.unpack()
        return datetime.datetime(*dt[:-1], microsecond=dt[-1]*1000)
LytroQueries[LytroQueryTime.query] = LytroQueryTime

class LytroQuerySize(LytroQuery):
    payloadstruct = '<I'
    length = 4
    query = 0
    params = (query,)
    def __init__(self, payload=None):
        self.payload = payload
    def size(self):
        return self.unpack()[0]
LytroQueries[LytroQuerySize.query] = LytroQuerySize

LytroResponses: Dict[int, Callable[[Any, bytes], Any]] = {}
LytroResponses[LytroQuery.command]=LytroQuery.response
class LytroLoad(LytroPacket):
    command=0xc2
    paramsstruct="B13x"
    def __init__(self, sort, path=None):
        assert sort in loadtypes.values()
        # pictures should be suffixed with a format digit: jpg,raw,txt,128,stk
        self.params=(sort,)
        if path is not None:
            self.payload=path
            self.length=len(path)+1  # NUL termination

class LytroDownload(LytroPacket):
    # TODO: Figure out why this fails over SCSI transport. 
    flags=1
    command=0xc4
    paramsstruct="BI8x"
    def __init__(self, length):
        self.params=[1,0]
        self.data=b""
        self.length = length
    @property
    def offset(self):
        return self.params[1]
    @offset.setter
    def offset(self, offset):
        self.params[1]=offset
    def send(self,s):
        LytroResponses[self.command]=self.receiveddata
        ret=super(LytroDownload,self).send(s)
        # Note: Increasing offset at send time is only helpful for pipelining.
        # If we do it in receiveddata, that provides a simple feedback for MTU. 
        #self.offset+=self.xferlength
        return ret
    def receiveddata(self, params, payload):
        self.data+=payload
        self.offset+=len(payload)
        #print(f"Got {len(payload)} bytes: {payload!r}")

# Hardware info
class HardwareInfo:
    def __init__(self, b):
        self.vendor, self.serial, self.build, self.swversion, self.unknown = (
            f.rstrip(b'\0') for f in struct.unpack('256s128s128s128s4s', b))
    def __str__(self):
        return str(self.__dict__)

class PictureRecord:
    structstring = '<8s8sII4x4x4x4xIf48s28sI'
    size = struct.calcsize(structstring)
    def __init__(self, b):
        f = struct.unpack(self.structstring, b)
        self.folderpostfix  = f[0].rstrip(b'\0')
        self.filenameprefix = f[1].rstrip(b'\0')
        self.folder         = f[2]
        self.file           = f[3]
        self.starred        = f[4]
        self.focus          = f[5]
        self.id             = f[6].rstrip(b'\0')
        self.datetime       = datetime.datetime.fromisoformat(f[7].rstrip(b'\0')
                                                              .decode('ascii').rstrip('Z'))
        self.rotation       = {1:0, 8:90, 3:180, 6:270}[f[8]]
        print(self.__dict__)
class PictureList(list):
    downloadtype='picture_list'
    def __init__(self, b):
        super(PictureList,self).__init__()
        header = struct.unpack('<3I', b[:12])
        assert header[0] == 1
        itemsize = header[1]
        recordsperitem = header[2]
        itemrecords = {
            struct.unpack('<I', b[o:o+4])[0]: struct.unpack('<I', b[o+4:o+8])[0]
            for o in range(12, 12+8*recordsperitem, 8)
        }
        #print(itemrecords)
        # I'm really not sure what these record things are. The picture records are
        # definitely a distinct thing. 
        self.extend(
            #{index*0:
            PictureRecord(b[base:base+PictureRecord.size])
             #for (index,offset) in itemrecords.items()}
            for base in range(12+8*recordsperitem, len(b), PictureRecord.size)
        )

class Lytro:
    def __init__(self, comm):
        self.comm = comm
    def getbattery(self):
        return LytroQueryBattery().send(self.comm).percent()
    def gettime(self):
        return LytroQueryTime().send(self.comm).datetime()
    def download(self, loadtype, name=None):
        load = LytroLoad(loadtypes[loadtype], name)
        load.send(self.comm)
        size = LytroQuerySize().send(self.comm).size()
        if size==0:
            raise FileNotFoundError(name)
        dl = LytroDownload(size)
        dl.send(self.comm)
        return dl.data
    def gethardwareinfo(self):
        data = self.download('hardware_info')
        return HardwareInfo(data)
    def getpicturelist(self):
        data = self.download('picture_list')
        return PictureList(data)

def connect(verbose=True):
    import comm_sg
    target: Optional[lytro.Target] = None

    if not target:
        for dev in comm_sg.probe():
            if verbose: print(f"Opening SCSI device {dev}")
            target = comm_sg.ScsiTarget(dev)

    import comm_usb
    if not target:
        for dev in comm_usb.probe():
            if verbose: print(f"Opening USB device {dev}")
            target = comm_usb.UsbTarget(dev)

    import comm_ip
    if not target:
        for addr in comm_ip.probe():
            if verbose: print(f"Connecting to IP device {addr}")
            target = comm_ip.IpTarget(addr)

    return Lytro(target)
