import datetime
import dateutil.parser
import struct
import time

# Protocol references:
#  http://optics.miloush.net/lytro/TheProtocols.Commands.aspx
#  https://ljirkovsky.wordpress.com/2015/03/16/lytro-protocol/

from typing import Dict, Callable, Any

# Abstract base class for communication modes
class Target:
    pass

# TODO: Clean ups; separate query and response, perhaps add response queue per connection

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
    paramsstruct="15x"
    params=()
    length=0
    payload=b''
    def send(self, s):
        assert struct.calcsize('<'+self.paramsstruct)==15, f"Bad length: {self.paramsstruct=}"
        packet=struct.pack('<B'+self.paramsstruct, self.command, *self.params)
        assert len(packet)==16, (struct.calcsize('<B'+self.paramsstruct), struct.calcsize('<'+self.paramsstruct), self.paramsstruct)
        if self.payload:
            data=self.payload.ljust(self.length,b'\0')
            #print(f"Write command: {packet!r} {data!r}")
            s.write(packet, data)
        else:
            #print(f"Read command: {packet!r} {self.length}")
            response=s.read(packet, self.length)
            if self.length and response:
                # Handle incoming data
                return self.read(self.command, packet[1:], response)
        return None
    @classmethod
    def read(self, command, params, payload):
        assert struct.calcsize('<'+self.paramsstruct)==15
        try:
            return LytroResponses[command](params,payload)
        except KeyError:
            raise IOError(f"Unknown packet: {params!r} {payload!r}")

LytroQueries = {}
class LytroQuery(LytroPacket):
    command=0xc6
    paramsstruct="xB13x"
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
        return datetime.datetime(*dt[:-1], microsecond=dt[-1]*1000, tzinfo=datetime.timezone.utc)
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

class LytroSetTime(LytroPacket):
    # FIXME does not yet work. On the plus side, doesn't crash camera either.
    command = 0xc0
    params = (4,)
    paramsstruct = ("xB13x",)
    def __init__(self, time):
        time = time.astimezone(datetime.timezone.utc)
        self.payload = struct.pack('<7H',
                                   time.year, time.month, time.day,
                                   time.hour, time.minute, time.second,
                                   time.microsecond//1000)

LytroResponses: Dict[int, Callable[[Any, bytes], Any]] = {}
LytroResponses[LytroQuery.command]=LytroQuery.response
class LytroLoad(LytroPacket):
    command=0xc2
    paramsstruct="xB13x"
    def __init__(self, sort, path=None):
        assert sort in loadtypes.values()
        # pictures should be suffixed with a format digit: jpg,raw,txt,128,stk
        self.params=(sort,)
        if path is not None:
            self.payload=path.encode('ascii')+b'\0'
            self.length=len(path)+1  # NUL termination

class LytroDownload(LytroPacket):
    # TODO: Figure out why this fails over SCSI transport. 
    command=0xc4
    paramsstruct="xBI9x"
    def __init__(self, length):
        #print(f"{struct.calcsize('<'+self.paramsstruct)=}")
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
        self.data = b""
        ret=super(LytroDownload,self).send(s)
        # Note: Increasing offset at send time is only helpful for pipelining.
        # If we do it in receiveddata, that provides a simple feedback for MTU. 
        #self.offset+=self.xferlength
        return ret
    def receiveddata(self, params, payload):
        #print(f"{params=}")
        self.data = payload
        self.offset += len(payload)
        #time.sleep(0.05)
        #self.params[0]^=1
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
        self.folderpostfix  = f[0].rstrip(b'\0').decode('ascii')
        self.filenameprefix = f[1].rstrip(b'\0').decode('ascii')
        self.folder         = f[2]
        self.file           = f[3]
        self.starred        = f[4]
        self.focus          = f[5]
        self.id             = f[6].rstrip(b'\0').decode('ascii')
        self.datetime       = dateutil.parser.isoparse(f[7].rstrip(b'\0').decode('ascii'))
        self.rotation       = {1:0, 8:90, 3:180, 6:270}[f[8]]
        #print(self.__dict__)
    def pathname(self, extension="RAW"):
        "Return an internal filename in Lytro F01, usable with file download. Not needed since picture download works with id (hash)."
        # Basic problem: formatting is for strings, and we have a lot of bytes. Simple solution: decode and encode. 
        return rf"I:\DCIM\{self.folder:03}{self.folderpostfix}\{self.filenameprefix}{self.file:04}.{extension}"
    def __str__(self):
        return f"{self.pathname()} {self.starred=} {self.id} {self.rotation=} {self.datetime}"
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
        # Need a better concept of what the item records mean.
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
    def settime(self, time=None):
        LytroSetTime(datetime.datetime.utcnow() if time is None else time.astimezone(datetime.timezone.utc))
    def download(self, loadtype, name=None, subtype=None, verbose=True):
        if loadtype=='picture' and subtype is not None:
            name += chr(picturesubtypes.index(subtype))
        load = LytroLoad(loadtypes[loadtype], name)
        load.send(self.comm)
        size = LytroQuerySize().send(self.comm).size()
        if size==0:
            raise FileNotFoundError(name)
        dl = LytroDownload(size)
        received = 0
        data = []
        while received < size:
            dl.offset = received
            dl.send(self.comm)

            if not dl.data:
                continue
            assert len(dl.data)>0
            data.append(dl.data)
            received += len(dl.data)
            #dl.params[0] ^= 1
            # FIXME: This may need delays for slow loading data!
            if verbose:
                print(f"\rDownload: got {received}/{size} bytes", flush=True, end='')
        if verbose:
            print()
        # Future improvement: Download must check which block is actually returned,
        # and could write in correct position using buffer memoryviews.
        # PyUSB accepts memoryviews for read. SG accepts a pointer, so memoryview is OK.
        # sockets have recv_into. 
        return b''.join(data)[:size]
    def gethardwareinfo(self):
        data = self.download('hardware_info')
        return HardwareInfo(data)
    def getpicturelist(self):
        data = self.download('picture_list')
        return PictureList(data)

def probe(verbose=True):
    import traceback

    try:
        import comm_sg
        for dev in comm_sg.probe():
            if verbose: print(f"Opening SCSI device {dev}")
            yield comm_sg.ScsiTarget(dev)
    except (ImportError, IOError):
        traceback.print_exc()

    try:
        import comm_usb
        for dev in comm_usb.probe():
            if verbose: print(f"Opening USB device {dev!r}")
            yield comm_usb.UsbTarget(dev)
    except (ImportError, IOError):
        traceback.print_exc()

    try:
        import comm_ip
        for addr in comm_ip.probe():
            if verbose: print(f"Connecting to IP device {addr}")
            yield comm_ip.IpTarget(addr)
    except (ImportError, IOError):
        traceback.print_exc()

def connect(verbose=True):
    target = next(probe(verbose=verbose))
    return Lytro(target)
