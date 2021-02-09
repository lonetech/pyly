import struct

# Abstract base class for communication modes
class Target:
    def __init__(self):
        raise InternalError("Abstract class")

# Download IDs
kind = {
    'hardware_info': 0,
    'file': 1,
    'picturelist': 2,
    'picture': 5,
    'calibration': 6,
    'rawcompressedpicture': 7
}

# Hardware info
class HardwareInfo:
    def __init__(self, b):
        self.vendor, self.serial, self.build, self.swversion, self.unknown = (
            f.rstrip(b'\0') for f in struct.unpack('256s128s128s128s4s', b))
    def __str__(self):
        return str(self.__dict__)

