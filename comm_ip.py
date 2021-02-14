#-*-coding:utf-8;-*-
#qpy:2
#qpy:console

import socket, struct
from collections import namedtuple
import lytro

magic = 0xfaaa55af
Response = namedtuple('Response', ['magic', 'size', 'seq', 'command'])

class IpTarget(lytro.Target):
    def __init__(self, address, timeout=1):
        self.s = socket.create_connection(address, timeout)
        self.s.settimeout(timeout)
    def read(self, command, size):
        prefix=struct.pack(b'<3I', magic, size, 1)
        self.s.send(prefix+command)
        response_s=self.s.recv(3*4+len(command))
        response=Response(*struct.unpack(b'<3IB', response_s[:13]))
        # Check that the response does match
        #print(f"Response: {response!r} {response_s!r}")
        assert response.magic == magic
        assert response.command == command[0]
        payload=self.s.recv(response.size)
        while len(payload)<response.size:
            payload+=self.s.recv(response.size-len(payload))
        return payload
    def write(self, command, data):
        prefix=struct.pack(b'<3I', magic, len(data), 0)
        self.s.send(prefix+command+data)
        response=self.s.recv(3*4+len(command))
        # Check that the response does match
        #print(f"Response: {response!r}")
        assert response[:3*4+1]==struct.pack(b'<3IB', magic, len(data), 2, command[0])
        return response[3*4+len(command):]

def probe():
    # TODO: Check if it's actually there? DNS-SD should be used. 
    return [("10.100.1.1", 5678)]
