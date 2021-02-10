#-*-coding:utf-8;-*-
#qpy:2
#qpy:console

#print "This is console module"

import lytro

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Access a Lytro F01 camera.')
    args = parser.parse_args()

    dev = lytro.connect()
    battery = dev.getbattery()
    print(f"Battery level: {battery}")
    dt = dev.gettime()
    print(f"Camera time: {dt}")
    info = dev.gethardwareinfo()
    print(info)
    print(dev.getpicturelist())

'''
    if len(argv)>=2:
      kind=int(argv[1])
      LytroLoad(kind, *[a.encode('ascii') for a in argv[2:3]]).send(target)
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

'''