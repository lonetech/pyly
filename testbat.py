#-*-coding:utf-8;-*-
#qpy:2
#qpy:console

#print "This is console module"

import struct, time
from typing import Dict, Optional, Callable, Any
import lytro

LytroResponses: Dict[int, Callable[[Any, bytes], Any]] = {}
class LytroPacket(object):
  headerstruct="<IIIH"
  paramsstruct="14x"
  params=()
  magic=0xfaaa55af
  length=0
  flags=0
  payload=b''
  def send(self, s):
    packet=struct.pack('Bx'+self.paramsstruct, 
    	      self.command, *self.params)
    if not self.flags&1:
      data=self.payload.ljust(self.length,b'\0')
      print("Write command: %r %r"%(packet, data))
      s.write(packet, data)
    else:
      print("Read command: %r %r"%(packet, self.length))
      response=s.read(packet, self.length)
      if self.length and response:
        return self.read(self.command, packet[2:], response)
  @classmethod
  def read(self, command, params, payload):
    #headersize=struct.calcsize(self.headerstruct)
    #paramssize=struct.calcsize('xx'+self.paramsstruct)
    #header=s.recv(headersize)
    header=None
    #params=response[:paramssize]
    #magic,length,flags,command=struct.unpack(self.headerstruct, header)
    #assert magic==self.magic, "Unknown magic in %r"%(header+params,)
    #assert flags&2, "Unexpected command %r"%(header+params,)
    #print "Command: %x length: %d flags: %x"%(command,length,flags)
    #payload=s.recv(length)
#    print "Header", len(header), repr(header)
#    print "Params", len(params), repr(params)
#    print "Payload", len(payload), repr(payload)
#    print "Rest", repr(s.recv(4096))
    try:
      return LytroResponses[command](params,payload)
    except KeyError as e:
      print("Unknown packet: ", repr((header,params,payload)))
class LytroQuery(LytroPacket):
  flags=1
  command=0xc6
  paramsstruct="B13x"
  @property
  def dllength(self):
    return struct.unpack("<I", self.payload)[0]
  def __init__(self, what, payload=None):
    # known queries: 0=content length, 3=camera time, 6=battery level)
    assert what in (0,3,6), "Unknown query type"
    sizes={0: 4, 3: 7*2, 6: 4}
    self.length=sizes[what]
    self.params=(what,)
    self.payload=payload
  def __str__(self):
    if self.params[0]==0:
      return "Length: %d"%struct.unpack("<I", self.payload)
    elif self.params[0]==3:
      return "Time: %r"%(struct.unpack("<7H", self.payload),)
    elif self.params[0]==6:
      return "Battery: %g"%struct.unpack("<f", self.payload)
  @classmethod
  def response(self, params, payload):
    (what,)=struct.unpack(self.paramsstruct, params)
    obj=self(what, payload)
    return obj
LytroResponses[LytroQuery.command]=LytroQuery.response
class LytroLoad(LytroPacket):
  command=0xc2
  paramsstruct="B13x"
  def __init__(self, sort, path=None):
    assert sort in (0,1,2,5,6,7)
    # hardware info, file, picture list, picture, calibration data, raw compressed picture
    # pictures should be suffixed with a format digit: jpg,raw,txt,128,stk
    self.params=(sort,)
    if path is not None:
      self.payload=path
      self.length=len(path)+1
class LytroDownload(LytroPacket):
  # TODO: Figure out why this fails over SCSI transport. 
  flags=1
  length=2048
  command=0xc4
  paramsstruct="BI8x"
  def __init__(self, length=2048):
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
    self.offset+=self.length
    #print "offset: ", self.offset
    return ret
  def receiveddata(self, params, payload):
    self.data+=payload
    #self.offset+=len(payload)
    print("Got data: ", len(payload), repr(payload))

#def recv(s):
#  try:
#    #print repr(s.recv(4096))
#    p=LytroPacket.read(s)
#    print p
#    return p
#  except socket.error, e:
#    print e
#    time.sleep(0.2)

target: Optional[lytro.Target] = None

import comm_usb
if not target:
  for dev in comm_usb.probe():
    target = comm_usb.UsbTarget(dev)

import comm_ip
if not target:
  for addr in comm_ip.probe():
    target = comm_ip.IpTarget(addr)

# SG transport fails at download.
#import comm_sg
#if not target:
#  for dev in comm_sg.probe():
#    target = comm_sg.ScsiTarget(dev)

from sys import argv
if len(argv)>=2:
  kind=int(argv[1])
  LytroLoad(kind, *argv[2:3]).send(target)
  #recv(target)   # no reply?
  p=LytroQuery(0).send(target)
  #p=recv(target)
  end=p.dllength
  print("Download for kind {} is {} bytes".format(kind,end))
  dl=LytroDownload(length=end)
  while len(dl.data)<end:
    dl.send(target)
    #recv(target)
    print(len(dl.data))
  if len(argv)>=4:
    open(argv[3],"wb").write(dl.data)
  else:
    print(repr(dl.data))
else:
  while True:
    time.sleep(3)
    for kind in 6,3,0:
      print(LytroQuery(kind).send(target))
