#-*-coding:utf-8;-*-
#qpy:2
#qpy:console

import socket, struct

magic = 0xfaaa55af

class IpTarget:
    def __init__(self, address):
        self.s = socket.create_connection(address)
        self.s.settimeout(5)
    def read(self, command, size):
        prefix=struct.pack('<3I', magic, size, 1)
        self.s.send(prefix+command)
        response=self.s.recv(3*4+len(command)+size)
        # Check that the response does match
        assert response[:3*4+1]==struct.pack('<3Ic', magic, size, 2, command[0])
        return response[3*4+len(command):]
    def write(self, command, data):
        prefix=struct.pack('<3I', magic, size, 0)
        self.s.send(prefix+command+data)

def probe():
    return [("10.100.1.1", 5678)]
